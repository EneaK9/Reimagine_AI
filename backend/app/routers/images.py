"""
ReimagineAI - Images Router
Handles room redesign using Gemini for image editing
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from typing import Optional, List
import base64
import traceback

from ..deps import check_base64_size, get_current_user, read_upload_limited
from ..models.schemas import (
    ImageGenerationRequest,
    ImageGenerationResponse,
    GeneratedImage,
    DesignStyle
)
from ..services.gemini_service import gemini_service

router = APIRouter(prefix="/images", tags=["Images"])


@router.get("/styles")
async def get_available_styles(current_user: dict = Depends(get_current_user)):
    """
    Get list of available interior design styles.
    """
    return {
        "styles": gemini_service.get_available_styles(),
        "default": "modern"
    }


@router.post("/generate", response_model=ImageGenerationResponse)
async def generate_images(
    request: ImageGenerationRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Generate room design images from a text prompt only (no reference image).
    Uses Gemini for text-to-image generation.
    """
    check_base64_size(request.reference_image_base64)
    # The schema allows "style": null; fall back to the default style
    style = (request.style or DesignStyle.MODERN).value
    styled_prompt = f"{request.prompt}. Style: {style}"

    try:
        # Use Gemini for text-only generation
        image_urls = await gemini_service.generate_from_prompt(
            prompt=styled_prompt,
            style=style,
            num_outputs=request.num_variations
        )
    except Exception:
        print("[Images] Text-to-image generation failed:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Image generation failed")

    generated_images = [
        GeneratedImage(
            url=url,
            prompt_used=styled_prompt,
            style=style
        )
        for url in image_urls
    ]

    return ImageGenerationResponse(images=generated_images)


@router.post("/analyze")
async def analyze_room(
    image: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    """
    Analyze a room image using GPT-4 Vision.
    Returns room type, current style, furniture, and suggestions.
    """
    from ..services.openai_service import openai_service

    image_content = await read_upload_limited(image)
    image_base64 = base64.b64encode(image_content).decode('utf-8')

    try:
        return await openai_service.analyze_room_image(image_base64)
    except Exception:
        print("[Images] Room analysis failed:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Room analysis failed")


@router.post("/redesign")
async def redesign_room(
    image: UploadFile = File(...),
    style: str = Form("modern"),
    description: str = Form(""),
    preserve_structure: float = Form(0.7),
    current_user: dict = Depends(get_current_user),
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
    # Read and encode image
    image_content = await read_upload_limited(image)
    image_base64 = base64.b64encode(image_content).decode('utf-8')

    try:
        # Generate redesigned images using Gemini
        image_urls = await gemini_service.redesign_room(
            image_base64=image_base64,
            style=style,
            custom_prompt=description,
            num_outputs=4
        )
    except Exception:
        print("[Images] Redesign failed:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Room redesign failed")

    return {
        "success": True,
        "style_applied": style,
        "description": description,
        "images": image_urls,
        "count": len(image_urls),
        "method": "gemini"
    }


@router.post("/redesign/with-analysis")
async def redesign_with_analysis(
    image: UploadFile = File(...),
    style: str = Form("modern"),
    description: str = Form(""),
    current_user: dict = Depends(get_current_user),
):
    """
    Full redesign flow: Analyze room first, then redesign.
    Returns both the analysis and redesigned images.
    """
    from ..services.openai_service import openai_service

    image_content = await read_upload_limited(image)
    image_base64 = base64.b64encode(image_content).decode('utf-8')

    try:
        # Step 1: Analyze with GPT-4 Vision
        analysis = await openai_service.analyze_room_image(image_base64)

        # Step 2: Redesign with Gemini
        image_urls = await gemini_service.redesign_room(
            image_base64=image_base64,
            style=style,
            custom_prompt=description,
            num_outputs=4
        )
    except Exception:
        print("[Images] Redesign with analysis failed:")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Room redesign failed")

    return {
        "success": True,
        "analysis": analysis,
        "style_applied": style,
        "images": image_urls,
        "count": len(image_urls)
    }
