"""
ReimagineAI - Depth Estimation and 3D Mesh Router
Handles photo-to-3D mesh generation endpoints
"""
import os
import base64
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from typing import Optional
from datetime import datetime

from ..models.schemas import (
    MeshGenerationRequest,
    MeshGenerationResponse,
    MeshInfo
)
from ..services.depth_service import depth_service
from ..services.conversation_service import conversation_service

router = APIRouter(prefix="/depth", tags=["Depth & 3D Mesh"])


@router.post("/generate-mesh", response_model=MeshGenerationResponse)
async def generate_mesh_from_photo(request: MeshGenerationRequest):
    """
    Generate a 3D mesh from a room photo using depth estimation.
    
    The process:
    1. Run MiDaS depth estimation on the photo
    2. Convert depth map to 3D point cloud
    3. Generate mesh using Open3D
    4. Export as GLB file
    
    Returns the mesh URL and depth map visualization.
    """
    try:
        # Generate mesh from image
        result = await depth_service.generate_mesh_from_image(request.image_base64)
        
        # Store mesh reference in conversation if provided
        if request.conversation_id:
            conversation_service.store_mesh_reference(
                request.conversation_id,
                result["mesh_id"]
            )
        
        # Build mesh URL (will be served from /depth/mesh/{mesh_id})
        mesh_url = f"/api/v1/depth/mesh/{result['mesh_id']}"
        
        return MeshGenerationResponse(
            mesh_id=result["mesh_id"],
            mesh_url=mesh_url,
            depth_map_url=result["depth_map_url"],
            conversation_id=request.conversation_id,
            original_size=result["original_size"]
        )
        
    except RuntimeError as e:
        raise HTTPException(
            status_code=503, 
            detail=f"Depth service not available: {str(e)}"
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-mesh/upload", response_model=MeshGenerationResponse)
async def generate_mesh_from_upload(
    image: UploadFile = File(...),
    conversation_id: Optional[str] = Form(None)
):
    """
    Generate a 3D mesh from an uploaded image file.
    Alternative to base64 encoding in the request body.
    """
    try:
        # Read and encode image
        image_content = await image.read()
        image_base64 = base64.b64encode(image_content).decode('utf-8')
        
        # Create request and delegate to main handler
        request = MeshGenerationRequest(
            image_base64=image_base64,
            conversation_id=conversation_id
        )
        
        return await generate_mesh_from_photo(request)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/mesh/{mesh_id}")
async def get_mesh(mesh_id: str):
    """
    Download a generated mesh file (GLB format).
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
async def get_mesh_info(mesh_id: str):
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
async def delete_mesh(mesh_id: str):
    """
    Delete a generated mesh.
    """
    success = depth_service.delete_mesh(mesh_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Mesh not found")
    
    return {"status": "deleted", "mesh_id": mesh_id}


@router.get("/meshes")
async def list_meshes():
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
async def update_mesh_from_edited_image(request: MeshGenerationRequest):
    """
    Regenerate a mesh from an edited image.
    Used after AI image editing to update the 3D view.
    
    This endpoint is called automatically when an image is edited
    and the conversation has an associated mesh.
    """
    # Same as generate_mesh, but specifically for updates
    return await generate_mesh_from_photo(request)
