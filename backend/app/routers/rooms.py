"""
ReimagineAI - Rooms Router
API endpoints for 3D room scanning and editing
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from fastapi.responses import FileResponse
from typing import Optional
from pydantic import BaseModel
import os

from ..services.room_service import room_service
from ..services.openai_service import openai_service

router = APIRouter(prefix="/rooms", tags=["rooms"])


# ============ Request/Response Models ============

class EditRequest(BaseModel):
    message: str  # Natural language edit request
    selected_part: Optional[str] = None  # Currently selected part in viewer


class EditResponse(BaseModel):
    edit: dict  # {"target": "wall", "property": "color", "value": "#001F3F"}
    ai_response: str


class TextureRequest(BaseModel):
    prompt: str  # Description of desired texture
    style: Optional[str] = "realistic"


class TextureResponse(BaseModel):
    texture: str  # Base64 encoded texture image


class RoomResponse(BaseModel):
    id: str
    name: str
    file_path: str
    created_at: str
    metadata: Optional[dict] = None


# ============ Endpoints ============

@router.post("/upload", response_model=RoomResponse)
async def upload_room(
    file: UploadFile = File(...),
    name: Optional[str] = Form(None)
):
    """
    Upload a scanned room glTF/GLB model
    
    - **file**: The 3D model file (GLB or glTF format)
    - **name**: Optional name for the room
    """
    # Validate file type
    allowed_extensions = ['.glb', '.gltf', '.obj']
    file_ext = os.path.splitext(file.filename)[1].lower() if file.filename else ''
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed types: {', '.join(allowed_extensions)}"
        )
    
    # Check file size (max 100MB)
    max_size = 100 * 1024 * 1024  # 100MB
    contents = await file.read()
    if len(contents) > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size is {max_size // (1024*1024)}MB"
        )
    
    # Reset file position
    await file.seek(0)
    
    # Save room
    room_name = name or f"Room Scan"
    room = await room_service.save_room(file, room_name)
    
    return RoomResponse(
        id=room['id'],
        name=room['name'],
        file_path=room['file_path'],
        created_at=room['created_at'],
        metadata=room.get('metadata')
    )


@router.get("/{room_id}", response_model=RoomResponse)
async def get_room(room_id: str):
    """
    Get room details and metadata
    """
    room = await room_service.get_room(room_id)
    
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    return RoomResponse(
        id=room['id'],
        name=room['name'],
        file_path=room['file_path'],
        created_at=room['created_at'],
        metadata=room.get('metadata')
    )


@router.get("/{room_id}/download")
async def download_room(room_id: str):
    """
    Download the room 3D model file
    """
    room = await room_service.get_room(room_id)
    
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    file_path = room['file_path']
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Room file not found")
    
    return FileResponse(
        file_path,
        media_type="model/gltf-binary",
        filename=os.path.basename(file_path)
    )


@router.get("")
async def list_rooms():
    """
    List all saved rooms
    """
    rooms = await room_service.list_rooms()
    return {"rooms": rooms}


@router.delete("/{room_id}")
async def delete_room(room_id: str):
    """
    Delete a room and its model file
    """
    success = await room_service.delete_room(room_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Room not found")
    
    return {"message": "Room deleted successfully"}


@router.post("/{room_id}/edit", response_model=EditResponse)
async def edit_room(room_id: str, request: EditRequest):
    """
    AI-powered room edit via natural language
    
    Parses the natural language request and returns structured edit commands
    that can be applied by the Unity viewer.
    
    Example requests:
    - "Make the walls navy blue"
    - "Change the floor to hardwood"
    - "Apply a marble texture to the countertop"
    """
    # Verify room exists
    room = await room_service.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    # Parse natural language with AI
    edit_command = await _parse_edit_request(
        request.message,
        request.selected_part
    )
    
    if not edit_command:
        raise HTTPException(
            status_code=400,
            detail="Could not understand edit request. Try something like 'Make the walls blue' or 'Change the floor to hardwood'."
        )
    
    # Generate response message
    target = edit_command.get('target', 'selected area')
    property_type = edit_command.get('property', 'appearance')
    value = edit_command.get('value', '')
    
    if property_type == 'color':
        ai_response = f"I've changed the {target} to {_describe_color(value)}."
    elif property_type == 'texture':
        ai_response = f"I've applied a {value} texture to the {target}."
    elif property_type == 'material':
        ai_response = f"I've applied a {value} finish to the {target}."
    else:
        ai_response = f"I've updated the {target}."
    
    return EditResponse(
        edit=edit_command,
        ai_response=ai_response
    )


@router.post("/{room_id}/generate-texture", response_model=TextureResponse)
async def generate_texture(room_id: str, request: TextureRequest):
    """
    Generate a new texture using AI based on description
    
    - **prompt**: Description of the desired texture
    - **style**: Style hint (realistic, stylized, etc.)
    """
    # Verify room exists
    room = await room_service.get_room(room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    # Generate texture using Gemini
    # TODO: Implement texture generation
    # For now, return a placeholder
    raise HTTPException(
        status_code=501,
        detail="Texture generation not yet implemented"
    )


# ============ Helper Functions ============

async def _parse_edit_request(message: str, selected_part: Optional[str] = None) -> Optional[dict]:
    """
    Parse natural language edit request into structured command using GPT-4
    """
    try:
        # Build context
        context = ""
        if selected_part:
            context = f"The user has selected: {selected_part}. "
        
        prompt = f"""{context}Parse this room edit request into a JSON command.

User request: "{message}"

Return JSON with:
- target: the part to edit (wall, floor, ceiling, furniture, door, window, or the specific part name)
- property: what to change (color, texture, material)
- value: the new value (hex color like #FF5733, or material name like "hardwood", or texture description)

Common colors and their hex values:
- white: #FFFFFF
- black: #000000
- red: #FF0000
- blue: #0000FF
- green: #00FF00
- navy/navy blue: #001F3F
- beige: #F5F5DC
- cream: #FFFDD0
- gray/grey: #808080
- brown: #8B4513
- tan: #D2B48C

Examples:
- "Make the walls navy blue" -> {{"target": "wall", "property": "color", "value": "#001F3F"}}
- "Change floor to hardwood" -> {{"target": "floor", "property": "material", "value": "hardwood"}}
- "Apply marble texture to the countertop" -> {{"target": "countertop", "property": "material", "value": "marble"}}

Return ONLY the JSON, no explanation."""

        response = await openai_service.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        
        if response:
            import json
            return json.loads(response)
        
        return None
        
    except Exception as e:
        print(f"[RoomsRouter] Error parsing edit request: {e}")
        
        # Fallback: Simple keyword parsing
        return _simple_parse_edit(message, selected_part)


def _simple_parse_edit(message: str, selected_part: Optional[str] = None) -> Optional[dict]:
    """
    Simple fallback parser using keywords
    """
    message_lower = message.lower()
    
    # Detect target
    target = None
    targets = ['wall', 'floor', 'ceiling', 'door', 'window', 'furniture']
    for t in targets:
        if t in message_lower:
            target = t
            break
    
    if not target and selected_part:
        target = selected_part
    
    if not target:
        return None
    
    # Detect color
    colors = {
        'white': '#FFFFFF',
        'black': '#000000',
        'red': '#FF0000',
        'blue': '#0000FF',
        'green': '#00FF00',
        'yellow': '#FFFF00',
        'navy': '#001F3F',
        'navy blue': '#001F3F',
        'beige': '#F5F5DC',
        'cream': '#FFFDD0',
        'gray': '#808080',
        'grey': '#808080',
        'brown': '#8B4513',
        'tan': '#D2B48C',
        'orange': '#FFA500',
        'pink': '#FFC0CB',
        'purple': '#800080',
        'teal': '#008080',
    }
    
    for color_name, hex_value in colors.items():
        if color_name in message_lower:
            return {
                'target': target,
                'property': 'color',
                'value': hex_value
            }
    
    # Detect material
    materials = ['wood', 'hardwood', 'marble', 'stone', 'metal', 'steel', 'glass', 'concrete', 'brick', 'tile']
    for material in materials:
        if material in message_lower:
            return {
                'target': target,
                'property': 'material',
                'value': material
            }
    
    return None


def _describe_color(hex_color: str) -> str:
    """
    Convert hex color to human-readable name
    """
    color_names = {
        '#FFFFFF': 'white',
        '#000000': 'black',
        '#FF0000': 'red',
        '#0000FF': 'blue',
        '#00FF00': 'green',
        '#FFFF00': 'yellow',
        '#001F3F': 'navy blue',
        '#F5F5DC': 'beige',
        '#FFFDD0': 'cream',
        '#808080': 'gray',
        '#8B4513': 'brown',
        '#D2B48C': 'tan',
        '#FFA500': 'orange',
        '#FFC0CB': 'pink',
        '#800080': 'purple',
        '#008080': 'teal',
    }
    
    hex_upper = hex_color.upper()
    return color_names.get(hex_upper, hex_color)
