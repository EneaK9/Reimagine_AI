"""
ReimagineAI - Scenes Router

Structured, editable 3D room scenes:
photo -> scene generation, catalog, edit ops, versions, natural-language edits.
"""
import base64
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..db.session import get_db
from ..deps import get_current_user
from ..models.scene import (
    SceneGenerationRequest,
    SceneNLEditRequest,
    SceneNLEditResponse,
    SceneOpsRequest,
    SceneResponse,
)
from ..services.catalog_service import catalog_service
from ..services.conversation_service import conversation_service
from ..services.generation_service import generation_service
from ..services.scene_builder import scene_builder
from ..services.scene_service import SceneServiceError, scene_service

router = APIRouter(prefix="/scenes", tags=["3D Scenes"])


@router.get("/assets/{filename}")
async def get_generated_asset(filename: str):
    """Serve a generated asset: furniture GLB or photo-sampled texture."""
    from fastapi.responses import FileResponse

    path = generation_service.asset_path(filename)
    if not path:
        raise HTTPException(status_code=404, detail="Asset not found")
    media_type = "image/jpeg" if filename.endswith(".jpg") else "model/gltf-binary"
    return FileResponse(path, media_type=media_type)


@router.get("/catalog")
async def get_catalog():
    """Furniture catalog used by the 3D editor (procedural builders + dims)."""
    return catalog_service.get_catalog()


@router.post("/generate", response_model=SceneResponse)
async def generate_scene(
    request: SceneGenerationRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Build an editable 3D scene from a room photo:
    furniture detection + depth-based placement + catalog asset matching.
    """
    try:
        data, resized_image = await scene_builder.build_scene_from_image(request.image_base64)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Scene generation failed: {e}")

    scene = scene_service.create_scene(
        db,
        user_id=current_user["id"],
        data=data,
        conversation_id=request.conversation_id,
        title=request.title,
    )

    # Persist the photo so "Make realistic" can crop per-object images later
    try:
        generation_service.save_scene_image(scene.scene_id, resized_image)
    except Exception as e:
        print(f"[Scenes] Could not save scene image: {e}")

    if request.conversation_id:
        conversation_service.store_scene_reference(
            db, request.conversation_id, scene.scene_id, user_id=current_user["id"]
        )

    return scene


@router.post("/generate/upload", response_model=SceneResponse)
async def generate_scene_from_upload(
    image: UploadFile = File(...),
    conversation_id: Optional[str] = Form(None),
    title: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Multipart variant of /generate."""
    image_content = await image.read()
    request = SceneGenerationRequest(
        image_base64=base64.b64encode(image_content).decode("utf-8"),
        conversation_id=conversation_id,
        title=title,
    )
    return await generate_scene(request, db, current_user)


@router.get("")
async def list_scenes(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List the current user's scenes."""
    return {"scenes": scene_service.list_scenes(db, current_user["id"])}


@router.get("/{scene_id}", response_model=SceneResponse)
async def get_scene(
    scene_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    scene = scene_service.get_scene(db, scene_id, current_user["id"])
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    return scene


@router.post("/{scene_id}/ops", response_model=SceneResponse)
async def apply_scene_ops(
    scene_id: str,
    request: SceneOpsRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Apply edit operations (move/rotate/recolor/swap/add/remove/set_room)."""
    try:
        return scene_service.apply_ops(db, scene_id, request.ops, current_user["id"])
    except SceneServiceError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{scene_id}/nl-edit", response_model=SceneNLEditResponse)
async def natural_language_edit(
    scene_id: str,
    request: SceneNLEditRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Apply a plain-English edit ("move the sofa to the back wall")."""
    scene, ops, message = await scene_service.nl_edit(
        db, scene_id, request.instruction, current_user["id"]
    )
    if scene is None:
        raise HTTPException(status_code=404, detail="Scene not found")
    return SceneNLEditResponse(
        scene_id=scene.scene_id,
        version=scene.version,
        data=scene.data,
        applied_ops=ops,
        message=message,
    )


@router.get("/{scene_id}/versions")
async def list_scene_versions(
    scene_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    versions = scene_service.list_versions(db, scene_id, current_user["id"])
    return {"scene_id": scene_id, "versions": versions}


@router.post("/{scene_id}/revert/{version}", response_model=SceneResponse)
async def revert_scene(
    scene_id: str,
    version: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    scene = scene_service.revert(db, scene_id, version, current_user["id"])
    if not scene:
        raise HTTPException(status_code=404, detail="Scene or version not found")
    return scene


@router.post("/{scene_id}/enhance", response_model=SceneResponse)
async def enhance_scene(
    scene_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Replace procedural stand-in furniture with AI-generated 3D meshes:
    each detected object is cropped from the original photo and run through
    an image-to-3D model (fal.ai TRELLIS). Objects that fail keep their
    procedural model. Requires FAL_API_KEY.
    """
    import asyncio

    if not generation_service.enabled:
        raise HTTPException(
            status_code=400,
            detail=(
                "Image-to-3D generation is not configured. "
                "Add FAL_API_KEY to backend/.env (get one at fal.ai) and restart."
            ),
        )

    scene = scene_service.get_scene(db, scene_id, current_user["id"])
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    photo = generation_service.load_scene_image(scene_id)
    if photo is None:
        raise HTTPException(
            status_code=400,
            detail="Original photo not available for this scene (regenerate the room first).",
        )

    # Only objects detected from the photo (with a bbox) can be generated.
    # Flat/reflective items (rugs, mirrors) produce useless 3D meshes —
    # their procedural versions look better.
    SKIP_CATEGORIES = {"rug", "mirror"}
    candidates = [
        obj for obj in scene.data.objects
        if obj.asset.type == "catalog"
        and obj.source and obj.source.get("bbox")
        and obj.category not in SKIP_CATEGORIES
    ]
    if not candidates:
        raise HTTPException(status_code=400, detail="No photo-detected objects to enhance.")

    # 2 concurrent generations: higher parallelism trips fal.ai rate limits (403)
    semaphore = asyncio.Semaphore(2)

    async def generate(obj):
        x0, y0, x1, y1 = obj.source["bbox"]
        # Bboxes are in detection-image coordinates; the stored photo is
        # higher resolution — scale so small objects get real pixels.
        src_w, src_h = obj.source.get("img_size") or (photo.width, photo.height)
        sx, sy = photo.width / src_w, photo.height / src_h
        x0, y0, x1, y1 = x0 * sx, y0 * sy, x1 * sx, y1 * sy
        # Pad the crop a little for context
        pad_x, pad_y = int((x1 - x0) * 0.08), int((y1 - y0) * 0.08)
        crop = photo.crop((
            max(0, int(x0) - pad_x), max(0, int(y0) - pad_y),
            min(photo.width, int(x1) + pad_x), min(photo.height, int(y1) + pad_y),
        ))
        async with semaphore:
            url = await generation_service.image_to_glb(crop, label=obj.label)
        return obj.id, url

    results = await asyncio.gather(*(generate(o) for o in candidates))
    asset_urls = {obj_id: url for obj_id, url in results if url}

    if not asset_urls:
        raise HTTPException(
            status_code=502,
            detail="3D generation failed for all objects — check the fal.ai key/quota.",
        )

    updated = scene_service.update_asset_refs(db, scene_id, asset_urls, current_user["id"])
    print(f"[Scenes] Enhanced {len(asset_urls)}/{len(candidates)} objects in {scene_id}")
    return updated


@router.delete("/{scene_id}")
async def delete_scene(
    scene_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    if not scene_service.delete_scene(db, scene_id, current_user["id"]):
        raise HTTPException(status_code=404, detail="Scene not found")
    return {"status": "deleted", "scene_id": scene_id}
