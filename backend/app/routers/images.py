"""
ReimagineAI - Images Router
Handles room redesign using Gemini for image editing
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query
from typing import Optional, List
import base64

from ..models.schemas import (
    ImageGenerationRequest,
    ImageGenerationResponse,
    GeneratedImage,
    DesignStyle
)
from ..services.gemini_service import gemini_service

router = APIRouter(prefix="/images", tags=["Images"])


@router.get("/styles")
async def get_available_styles():
    """
    Get list of available interior design styles.
    """
    return {
        "styles": gemini_service.get_available_styles(),
        "default": "modern"
    }


@router.post("/generate", response_model=ImageGenerationResponse)
async def generate_images(request: ImageGenerationRequest):
    """
    Generate room design images from a text prompt only (no reference image).
    Uses Gemini for text-to-image generation.
    """
    try:
        styled_prompt = f"{request.prompt}. Style: {request.style.value}"
        
        # Use Gemini for text-only generation
        image_urls = await gemini_service.generate_from_prompt(
            prompt=styled_prompt,
            style=request.style.value,
            num_outputs=request.num_variations
        )
        
        generated_images = [
            GeneratedImage(
                url=url,
                prompt_used=styled_prompt,
                style=request.style.value
            )
            for url in image_urls
        ]
        
        return ImageGenerationResponse(images=generated_images)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze")
async def analyze_room(image: UploadFile = File(...)):
    """
    Analyze a room image using GPT-4 Vision.
    Returns room type, current style, furniture, and suggestions.
    """
    from ..services.openai_service import openai_service
    
    try:
        image_content = await image.read()
        image_base64 = base64.b64encode(image_content).decode('utf-8')
        
        analysis = await openai_service.analyze_room_image(image_base64)
        
        return analysis
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/redesign")
async def redesign_room(
    image: UploadFile = File(...),
    style: str = Form("modern"),
    description: str = Form(""),
    preserve_structure: float = Form(0.7),
):
    """
    🎨 MAIN ENDPOINT: Redesign a room using Gemini.
    
    This transforms the room's style while keeping its basic structure.
    
    Args:
        image: Room photo to redesign
        style: Design style (modern, minimalist, industrial, etc.)
        description: Additional custom instructions
        preserve_structure: Not used with Gemini (kept for API compatibility)
    
    Returns:
        4 redesigned versions of the room
    """
    try:
        # Read and encode image
        image_content = await image.read()
        image_base64 = base64.b64encode(image_content).decode('utf-8')
        
        # Generate redesigned images using Gemini
        image_urls = await gemini_service.redesign_room(
            image_base64=image_base64,
            style=style,
            custom_prompt=description,
            num_outputs=4
        )
        
        return {
            "success": True,
            "style_applied": style,
            "description": description,
            "images": image_urls,
            "count": len(image_urls),
            "method": "gemini"
        }
        
    except Exception as e:
        print(f"Redesign error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/redesign/with-analysis")
async def redesign_with_analysis(
    image: UploadFile = File(...),
    style: str = Form("modern"),
    description: str = Form(""),
):
    """
    Full redesign flow: Analyze room first, then redesign.
    Returns both the analysis and redesigned images.
    """
    from ..services.openai_service import openai_service
    
    try:
        image_content = await image.read()
        image_base64 = base64.b64encode(image_content).decode('utf-8')
        
        # Step 1: Analyze with GPT-4 Vision
        analysis = await openai_service.analyze_room_image(image_base64)
        
        # Step 2: Redesign with Gemini
        image_urls = await gemini_service.redesign_room(
            image_base64=image_base64,
            style=style,
            custom_prompt=description,
            num_outputs=4
        )
        
        return {
            "success": True,
            "analysis": analysis,
            "style_applied": style,
            "images": image_urls,
            "count": len(image_urls)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
