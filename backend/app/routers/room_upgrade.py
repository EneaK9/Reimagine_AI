"""
Room upgrade router.
Coordinates photo analysis, product search, budget optimization, and image generation.
Uses multi-image fusion to place actual product images into the scene.
"""
import asyncio
import base64
from typing import List, Optional

import httpx
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from ..models.schemas import (
    RoomUpgradeAnalyzeRequest,
    RoomUpgradeAnalyzeResponse,
    RoomUpgradeGenerateRequest,
    RoomUpgradeGenerateResponse,
    RoomUpgradeSearchRequest,
    SelectedProduct,
)
from ..services.budget_optimizer_service import budget_optimizer_service
from ..services.gemini_service import gemini_service
from ..services.product_search_service import product_search_service
from ..services.scene_analysis_service import scene_analysis_service

router = APIRouter(prefix="/room-upgrade", tags=["Room Upgrade"])


@router.post("/analyze", response_model=RoomUpgradeAnalyzeResponse)
async def analyze_room_upgrade(request: RoomUpgradeAnalyzeRequest):
    """
    Full preparation flow: analyze the uploaded space, search products,
    and select a product combination that fits the user's budget.
    """
    try:
        budget = request.budget or scene_analysis_service.parse_budget(request.prompt)
        if budget is None or budget <= 0:
            raise HTTPException(status_code=400, detail="Please include a valid budget.")

        scene_analysis = await scene_analysis_service.analyze_scene(
            image_base64=request.image_base64,
            prompt=request.prompt,
            budget=budget,
            currency=request.currency,
        )

        search_results = await asyncio.gather(
            *[
                product_search_service.search_with_fallback(item)
                for item in scene_analysis.shopping_list
            ]
        )
        search_results = [
            result for result in search_results if result.all_candidates
        ]

        selected_products, total, within_budget = await budget_optimizer_service.optimize(
            search_results,
            budget,
        )
        selected_products = await product_search_service.resolve_selected_product_links(
            selected_products
        )

        return RoomUpgradeAnalyzeResponse(
            scene_analysis=scene_analysis,
            search_results=search_results,
            selected_products=selected_products,
            total_estimated=total,
            within_budget=within_budget,
            budget=budget,
            currency=request.currency,
        )
    except HTTPException:
        raise
    except Exception as exc:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/analyze/upload", response_model=RoomUpgradeAnalyzeResponse)
async def analyze_room_upgrade_upload(
    prompt: str = Form(...),
    budget: Optional[float] = Form(None),
    currency: str = Form("USD"),
    image: UploadFile = File(...),
):
    """
    Multipart convenience endpoint for mobile clients.
    """
    image_content = await image.read()
    image_base64 = base64.b64encode(image_content).decode("utf-8")
    request = RoomUpgradeAnalyzeRequest(
        image_base64=image_base64,
        prompt=prompt,
        budget=budget,
        currency=currency,
    )
    return await analyze_room_upgrade(request)


@router.post("/search-products", response_model=RoomUpgradeAnalyzeResponse)
async def search_products_for_upgrade(request: RoomUpgradeSearchRequest):
    """
    Search and optimize products for a shopping list without re-analyzing the image.
    """
    try:
        search_results = await asyncio.gather(
            *[
                product_search_service.search_with_fallback(item)
                for item in request.shopping_list
            ]
        )
        search_results = [
            result for result in search_results if result.all_candidates
        ]
        selected_products, total, within_budget = await budget_optimizer_service.optimize(
            search_results,
            request.budget,
        )
        selected_products = await product_search_service.resolve_selected_product_links(
            selected_products
        )

        return RoomUpgradeAnalyzeResponse(
            scene_analysis={
                "space_type": "space",
                "existing_items": [],
                "style_observation": "",
                "shopping_list": request.shopping_list,
            },
            search_results=search_results,
            selected_products=selected_products,
            total_estimated=total,
            within_budget=within_budget,
            budget=request.budget,
            currency=request.currency,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/generate", response_model=RoomUpgradeGenerateResponse)
async def generate_room_upgrade(request: RoomUpgradeGenerateRequest):
    """
    Generate an after photo using the approved product list.
    Uses multi-image fusion: passes product reference images to Gemini
    so the actual products appear in the generated image.
    """
    try:
        image_base64 = _strip_data_url(request.image_base64)

        # Fetch product reference images for multi-image fusion
        print(f"Fetching {len(request.selected_products)} product images...")
        product_images = await fetch_product_images(request.selected_products)
        print(f"Successfully fetched {len(product_images)} product images")

        # Build prompt that references each product image by position
        prompt = build_room_upgrade_prompt_v2(request, len(product_images))

        # Use multi-image fusion if we have product images
        if product_images:
            generated_images = await gemini_service.edit_room_with_products(
                room_image_base64=image_base64,
                product_images=product_images,
                prompt=prompt,
            )
        else:
            # Fallback to text-only prompt
            print("No product images fetched, using text-only prompt")
            generated_images = await gemini_service.edit_room(
                image_base64=image_base64,
                edit_instruction=prompt,
                style="modern",
            )

        return RoomUpgradeGenerateResponse(
            after_image_url=generated_images[0] if generated_images else None,
            generated_images=generated_images,
            prompt_used=prompt,
        )
    except Exception as exc:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc))


async def fetch_product_images(
    selected_products: List[SelectedProduct],
    max_products: int = 6,
) -> List[bytes]:
    """
    Download product images for Gemini multi-image fusion.
    Returns list of image bytes, preserving order.
    """
    products_to_fetch = selected_products[:max_products]

    async def fetch_single(product: SelectedProduct) -> Optional[bytes]:
        # Prefer high-res image if available
        image_url = (
            product.chosen_product.high_res_image_url
            or product.chosen_product.image_url
        )
        if not image_url:
            return None

        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                response = await client.get(image_url)
                response.raise_for_status()
                content = response.content

                # Validate it's actually image data (check magic bytes)
                if content[:4] in (b'\xff\xd8\xff\xe0', b'\xff\xd8\xff\xe1',  # JPEG
                                   b'\x89PNG', b'RIFF', b'GIF8'):  # PNG, WebP, GIF
                    return content
                if content[:8].startswith(b'\x89PNG'):
                    return content

                # Accept if content-type says it's an image
                content_type = response.headers.get("content-type", "")
                if "image" in content_type:
                    return content

                print(f"Skipping non-image content from {image_url[:50]}...")
                return None

        except Exception as exc:
            print(f"Failed to fetch product image: {exc}")
            return None

    # Fetch all in parallel
    tasks = [fetch_single(product) for product in products_to_fetch]
    results = await asyncio.gather(*tasks)

    # Filter out None values while preserving corresponding product order
    return [img for img in results if img is not None]


def build_room_upgrade_prompt_v2(
    request: RoomUpgradeGenerateRequest,
    num_product_images: int,
) -> str:
    """
    Build prompt that references product images by position.
    Image 1 = room photo, Images 2-N = product photos.
    """
    item_descriptions = []

    for index, selected in enumerate(request.selected_products, start=1):
        product = selected.chosen_product
        item = selected.shopping_list_item

        # Build detailed product description
        details = []
        if product.material:
            details.append(f"made of {product.material}")
        if product.color:
            details.append(f"in {product.color}")
        if product.dimensions:
            details.append(f"size: {product.dimensions}")

        detail_str = f" ({', '.join(details)})" if details else ""

        # Reference the product image if available
        if index <= num_product_images:
            image_ref = f"[Use the EXACT product from Image {index + 1}]"
        else:
            image_ref = ""

        item_descriptions.append(
            f"{index}. {product.title}{detail_str}\n"
            f"   Store: {product.store}, Price: ${product.price:.2f}\n"
            f"   Placement: {item.placement}\n"
            f"   {image_ref}"
        )

    user_prompt = f"\nUser request: {request.prompt}" if request.prompt else ""

    # If we have product images, use multi-image prompt
    if num_product_images > 0:
        return f"""You are editing Image 1 (the room/outdoor space photo).{user_prompt}

I am providing {num_product_images} product reference images (Images 2-{num_product_images + 1}).
You MUST add these EXACT products to the scene - use their appearance from the reference images.

Products to add:

{chr(10).join(item_descriptions)}

CRITICAL RULES:
1. DO NOT change the camera angle, perspective, or viewpoint - keep EXACTLY the same view as the original photo
2. DO NOT regenerate or reimagine the space - ONLY add products to the existing photo
3. DO NOT add, replace, expand, or redesign any floor surface: no floor tiles, pavers, patio slabs, deck boards, concrete, gravel, rugs, or hardscape unless that exact product is listed
4. DO NOT replace grass with tiles or patio flooring. If there is grass in the original photo, it must remain grass
5. DO NOT add new pergolas, roofs, beams, walls, fences, pathways, raised beds, or landscaping structures
6. Use the EXACT visual appearance of each product from its reference image
7. Products must be CLEARLY VISIBLE in the final image - not subtle or hidden
8. Scale products appropriately for the existing visible surface; do not create a new support surface for them
9. Match lighting and shadows to the room
10. Place products naturally but prominently where specified
11. Preserve EVERYTHING in the original photo - walls, floors, grass, plants, furniture, architecture
12. NO labels, watermarks, text overlays, or price tags
13. The output should look like the SAME photo with products added, not a new photo

The space is a {request.scene_analysis.space_type}.
Current style: {request.scene_analysis.style_observation}

Generate the edited image now. Keep the EXACT same photo, just add the products."""

    # Fallback text-only prompt (when no product images available)
    return f"""You are editing the provided room or outdoor space photo.{user_prompt}

Add the following products to the photo naturally:

{chr(10).join(item_descriptions)}

CRITICAL RULES:
- DO NOT change the camera angle, perspective, or viewpoint - keep EXACTLY the same view
- DO NOT regenerate or reimagine the space - ONLY add products to the existing photo
- DO NOT add, replace, expand, or redesign any floor surface: no floor tiles, pavers, patio slabs, deck boards, concrete, gravel, rugs, or hardscape unless that exact product is listed
- DO NOT replace grass with tiles or patio flooring. If there is grass in the original photo, it must remain grass
- DO NOT add new pergolas, roofs, beams, walls, fences, pathways, raised beds, or landscaping structures
- Make products CLEARLY VISIBLE - they should be prominent in the scene
- Preserve EVERYTHING in the original photo - walls, floors, plants, furniture, architecture
- Match lighting direction and shadows
- Products should look physically present, not pasted
- No labels, watermarks, or text
- The output should look like the SAME photo with products added, not a new photo

The space is a {request.scene_analysis.space_type}.
Style: {request.scene_analysis.style_observation}

Keep the EXACT same photo, just add the products."""


def _strip_data_url(image_base64: str) -> str:
    if "," in image_base64 and image_base64.startswith("data:"):
        return image_base64.split(",", 1)[1]
    return image_base64
