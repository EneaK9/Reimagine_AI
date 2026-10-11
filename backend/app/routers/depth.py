"""
ReimagineAI - Depth Estimation and 3D Mesh Router
Handles photo-to-3D mesh generation endpoints
"""
import os
import base64
import asyncio
import binascii
import threading
import time
import traceback
from io import BytesIO
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from typing import Optional
from datetime import datetime
from PIL import Image, UnidentifiedImageError
from sqlalchemy.orm import Session

from ..db.session import get_db
from ..deps import check_base64_size, get_current_user, read_upload_limited
from ..models.schemas import (
    MeshGenerationRequest,
    MeshGenerationResponse,
    MeshInfo
)
from ..services.depth_service import depth_service
from ..services.conversation_service import conversation_service

router = APIRouter(prefix="/depth", tags=["Depth & 3D Mesh"])

# The MiDaS mesh pipeline is CPU/RAM heavy and its lazy model load is not
# thread-safe: run one job at a time, in a worker thread.
_mesh_lock = threading.Lock()


def _check_image_header(image_base64: str) -> None:
    """Cheap validity check (base64 + image header) so bad input fails before queueing."""
    payload = image_base64.split(",", 1)[1] if image_base64.startswith("data:") else image_base64
    Image.open(BytesIO(base64.b64decode(payload))).close()


def _build_mesh_sync(image_base64: str) -> dict:
    """
    Blocking image -> depth map -> GLB pipeline. Mirrors
    depth_service.generate_mesh_from_image (declared async but fully
    synchronous) so it can run via asyncio.to_thread, off the event loop.
    """
    _check_image_header(image_base64)

    with _mesh_lock:
        start_time = time.time()
        print("[Pipeline] Starting mesh generation pipeline...")

        depth_map, resized_image = depth_service.generate_depth_map(image_base64)
        print(f"[Pipeline] Depth map generated in {time.time() - start_time:.1f}s")

        # Viewable depth map
        depth_map_url = depth_service.depth_map_to_image(depth_map)

        # Texture the mesh with the resized image, not the original upload
        resized_base64 = depth_service._encode_image_base64(resized_image, 'PNG')
        mesh_id, mesh_path = depth_service.create_mesh_from_depth(resized_base64, depth_map)

        print(f"[Pipeline] Complete! Total time: {time.time() - start_time:.1f}s")

    return {
        "mesh_id": mesh_id,
        "mesh_path": mesh_path,
        "depth_map_url": depth_map_url,
        "original_size": {
            "width": resized_image.width,
            "height": resized_image.height
        }
    }


async def _generate_mesh(
    image_base64: str,
    conversation_id: Optional[str],
    db: Session,
    user_id: str,
) -> MeshGenerationResponse:
    """Build a mesh off the event loop and link it to the caller's conversation."""
    if not image_base64:
        raise HTTPException(status_code=400, detail="image_base64 is required")

    try:
        result = await asyncio.to_thread(_build_mesh_sync, image_base64)
    except (binascii.Error, UnidentifiedImageError):
        raise HTTPException(status_code=400, detail="Invalid image data")
    except Image.DecompressionBombError:
        raise HTTPException(status_code=413, detail="Image dimensions too large")
    except RuntimeError:
        # Raised when PyTorch / Open3D are unavailable
        print("[Depth] Mesh generation unavailable:")
        traceback.print_exc()
        raise HTTPException(status_code=503, detail="Depth service not available")
    except Exception:
        print("[Depth] Mesh generation failed:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Mesh generation failed")

    # Store mesh reference in the conversation (only if it belongs to the caller)
    if conversation_id:
        try:
            conversation_service.store_mesh_reference(
                db, conversation_id, result["mesh_id"], user_id=user_id
            )
        except Exception:
            # The mesh is built already; don't fail the request over the link
            db.rollback()
            print(f"[Depth] Could not link mesh {result['mesh_id']} to conversation {conversation_id}:")
            traceback.print_exc()

    # Build mesh URL (served from /depth/mesh/{mesh_id})
    mesh_url = f"/api/v1/depth/mesh/{result['mesh_id']}"

    return MeshGenerationResponse(
        mesh_id=result["mesh_id"],
        mesh_url=mesh_url,
        depth_map_url=result["depth_map_url"],
        conversation_id=conversation_id,
        original_size=result["original_size"]
    )


@router.post("/generate-mesh", response_model=MeshGenerationResponse)
async def generate_mesh_from_photo(
    request: MeshGenerationRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Generate a 3D mesh from a room photo using depth estimation.

    The process:
    1. Run MiDaS depth estimation on the photo
    2. Convert depth map to 3D point cloud
    3. Generate mesh using Open3D
    4. Export as GLB file

    Returns the mesh URL and depth map visualization.
    """
    check_base64_size(request.image_base64)
    return await _generate_mesh(
        request.image_base64, request.conversation_id, db, current_user["id"]
    )


@router.post("/generate-mesh/upload", response_model=MeshGenerationResponse)
async def generate_mesh_from_upload(
    image: UploadFile = File(...),
    conversation_id: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Generate a 3D mesh from an uploaded image file.
    Alternative to base64 encoding in the request body.
    """
    image_content = await read_upload_limited(image)
    image_base64 = base64.b64encode(image_content).decode('utf-8')
    return await _generate_mesh(image_base64, conversation_id, db, current_user["id"])


@router.get("/mesh/{mesh_id}")
async def get_mesh(mesh_id: str):
    """
    Download a generated mesh file (GLB format).
    Public on purpose: the app's <model-viewer> WebView loads it without an
    Authorization header. Mesh ids are random.
    """
    mesh_path = depth_service.get_mesh_path(mesh_id)

    if not mesh_path:
        raise HTTPException(status_code=404, detail="Mesh not found")

    return FileResponse(
        mesh_path,
        media_type="model/gltf-binary",
        filename=f"{mesh_id}.glb",
        headers={
            "Access-Control-Expose-Headers": "Content-Disposition"
        }
    )


@router.get("/mesh/{mesh_id}/info", response_model=MeshInfo)
async def get_mesh_info(
    mesh_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Get information about a generated mesh.
    """
    mesh_path = depth_service.get_mesh_path(mesh_id)

    if not mesh_path:
        raise HTTPException(status_code=404, detail="Mesh not found")

    file_size = os.path.getsize(mesh_path)
    file_mtime = os.path.getmtime(mesh_path)

    return MeshInfo(
        mesh_id=mesh_id,
        mesh_url=f"/api/v1/depth/mesh/{mesh_id}",
        size_bytes=file_size,
        created_at=datetime.fromtimestamp(file_mtime)
    )


@router.delete("/mesh/{mesh_id}")
async def delete_mesh(
    mesh_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Delete a generated mesh.
    """
    success = depth_service.delete_mesh(mesh_id)

    if not success:
        raise HTTPException(status_code=404, detail="Mesh not found")

    return {"status": "deleted", "mesh_id": mesh_id}


@router.get("/meshes")
async def list_meshes(current_user: dict = Depends(get_current_user)):
    """
    List all generated meshes.
    """
    meshes = depth_service.list_meshes()
    return {
        "meshes": [
            {
                "mesh_id": m["mesh_id"],
                "mesh_url": f"/api/v1/depth/mesh/{m['mesh_id']}",
                "size_bytes": m["size"]
            }
            for m in meshes
        ],
        "count": len(meshes)
    }


@router.post("/update-mesh", response_model=MeshGenerationResponse)
async def update_mesh_from_edited_image(
    request: MeshGenerationRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Regenerate a mesh from an edited image.
    Used after AI image editing to update the 3D view.

    This endpoint is called automatically when an image is edited
    and the conversation has an associated mesh.
    """
    # Same as generate_mesh, but specifically for updates
    check_base64_size(request.image_base64)
    return await _generate_mesh(
        request.image_base64, request.conversation_id, db, current_user["id"]
    )
