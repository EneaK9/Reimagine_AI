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
from ..services.scene_builder import scene_builder
from ..services.scene_service import SceneServiceError, scene_service

router = APIRouter(prefix="/scenes", tags=["3D Scenes"])


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
        data = await scene_builder.build_scene_from_image(request.image_base64)
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


@router.delete("/{scene_id}")
async def delete_scene(
    scene_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    if not scene_service.delete_scene(db, scene_id, current_user["id"]):
        raise HTTPException(status_code=404, detail="Scene not found")
    return {"status": "deleted", "scene_id": scene_id}
