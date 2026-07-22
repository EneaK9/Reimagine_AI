"""
ReimagineAI - Chat Router
Handles all chat-related endpoints (PostgreSQL-backed, user-scoped).
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from typing import Optional
import base64

from sqlalchemy.orm import Session

from ..models.schemas import (
    ChatRequest,
    ChatResponse,
    MessageRole,
    ConversationSummary,
)
from ..services.openai_service import openai_service
from ..services.conversation_service import conversation_service
from ..services.gemini_service import gemini_service
from ..services.depth_service import depth_service
from ..db.session import get_db
from ..deps import get_current_user

router = APIRouter(prefix="/chat", tags=["Chat"])


async def _handle_chat(
    request: ChatRequest,
    db: Session,
    user: dict,
) -> ChatResponse:
    user_id = user["id"]

    conversation = conversation_service.get_or_create_conversation(
        db, user_id, request.conversation_id
    )

    if request.mesh_id:
        print(f"[Chat] Mesh ID provided: {request.mesh_id} - enabling mesh editing mode")
        conversation_service.store_mesh_reference(
            db, conversation.id, request.mesh_id, user_id=user_id
        )

    image_to_edit = None
    is_follow_up = False

    if request.image_base64:
        image_to_edit = request.image_base64
        conversation_service.store_original_image(
            db, conversation.id, request.image_base64, user_id=user_id
        )
    else:
        last_image = conversation_service.get_last_generated_image(
            db, conversation.id, user_id=user_id
        )
        original_image = conversation_service.get_original_image(
            db, conversation.id, user_id=user_id
        )
        if last_image:
            image_to_edit = last_image
            is_follow_up = True
            print("Using last generated image for follow-up edit")
        elif original_image:
            image_to_edit = original_image
            is_follow_up = True
            print("Using original uploaded image for follow-up edit")

    user_image_url = None
    if request.image_base64:
        user_image_url = f"data:image/jpeg;base64,{request.image_base64}"

    conversation_service.add_message(
        db,
        conversation.id,
        MessageRole.USER,
        request.message,
        image_url=user_image_url,
        user_id=user_id,
    )

    context_messages = conversation_service.get_messages_for_context(
        db, conversation.id, user_id=user_id
    )

    ai_response = await openai_service.chat_completion(
        messages=context_messages,
        image_base64=request.image_base64,
    )

    generated_images = []
    image_error_note = None
    image_prompt = openai_service.extract_image_prompt(ai_response)
    wants_edit = (
        image_prompt
        or _is_edit_request(request.message)
        or (is_follow_up and _is_affirmative(request.message))
    )

    if image_to_edit and wants_edit:
        try:
            style = _extract_style_from_prompt(ai_response)
            edit_instruction = request.message
            if _is_affirmative(request.message) and image_prompt:
                edit_instruction = image_prompt
            elif _is_affirmative(request.message):
                edit_instruction = (
                    _last_user_edit_request(context_messages) or request.message
                )

            generated_images = await gemini_service.edit_room(
                image_base64=image_to_edit,
                edit_instruction=edit_instruction,
                style=style,
            )
            if not generated_images:
                image_error_note = (
                    "I understood the change, but image editing didn’t return a result "
                    "(the image model may be rate-limited or out of quota). "
                    "Please try again in a minute, or check your Gemini API billing/quota."
                )
        except Exception as img_error:
            print(f"Image generation failed: {img_error}")
            import traceback

            traceback.print_exc()
            image_error_note = (
                f"I couldn’t update the image right now: {_friendly_image_error(img_error)}"
            )

    if image_error_note:
        ai_response = f"{ai_response}\n\n⚠️ {image_error_note}"

    conversation_service.add_message(
        db,
        conversation.id,
        MessageRole.ASSISTANT,
        ai_response,
        user_id=user_id,
    )

    mesh_url = None
    mesh_id = None

    if generated_images:
        last_img = generated_images[0]
        if last_img.startswith("data:"):
            last_img_base64 = last_img.split(",", 1)[1]
        else:
            last_img_base64 = last_img

        conversation_service.update_conversation_with_images(
            db,
            conversation.id,
            generated_images,
            last_image_base64=last_img_base64,
            user_id=user_id,
        )

        if conversation_service.has_mesh(db, conversation.id, user_id=user_id):
            try:
                print(f"[Chat] Regenerating mesh for conversation {conversation.id}")
                mesh_result = await depth_service.generate_mesh_from_image(
                    last_img_base64
                )
                mesh_id = mesh_result["mesh_id"]
                conversation_service.store_mesh_reference(
                    db, conversation.id, mesh_id, user_id=user_id
                )
                mesh_url = f"/api/v1/depth/mesh/{mesh_id}"
                print(f"[Chat] Mesh regenerated: {mesh_url}")
            except Exception as mesh_error:
                print(f"[Chat] Mesh regeneration failed: {mesh_error}")
                import traceback

                traceback.print_exc()
    else:
        existing_mesh_id = conversation_service.get_mesh_id(
            db, conversation.id, user_id=user_id
        )
        if existing_mesh_id:
            mesh_id = existing_mesh_id
            mesh_url = f"/api/v1/depth/mesh/{mesh_id}"

    clean_response = ai_response
    if "[IMAGE_PROMPT]" in clean_response:
        clean_response = clean_response.split("[IMAGE_PROMPT]")[0].strip()

    return ChatResponse(
        conversation_id=conversation.id,
        message=clean_response,
        generated_images=generated_images,
        furniture_suggestions=[],
        mesh_url=mesh_url,
        mesh_id=mesh_id,
    )


@router.post("/", response_model=ChatResponse)
async def send_message(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Send a message to the AI assistant (requires auth)."""
    try:
        return await _handle_chat(request, db, current_user)
    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/with-image", response_model=ChatResponse)
async def send_message_with_image(
    message: str = Form(...),
    conversation_id: Optional[str] = Form(None),
    mesh_id: Optional[str] = Form(None),
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Send a message with an uploaded image file (requires auth)."""
    try:
        image_content = await image.read()
        image_base64 = base64.b64encode(image_content).decode("utf-8")
        request = ChatRequest(
            message=message,
            conversation_id=conversation_id,
            image_base64=image_base64,
            mesh_id=mesh_id,
        )
        return await _handle_chat(request, db, current_user)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversations")
async def list_conversations(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get conversations for the authenticated user."""
    conversations = conversation_service.list_conversations(db, current_user["id"])
    return [
        ConversationSummary(
            id=conv.id,
            title=conv.title,
            last_message=conv.messages[-1].content if conv.messages else None,
            image_count=len([m for m in conv.messages if m.image_url]),
            created_at=conv.created_at,
            updated_at=conv.updated_at,
        )
        for conv in conversations
    ]


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get a specific conversation owned by the current user."""
    conversation = conversation_service.get_conversation(
        db, conversation_id, current_user["id"]
    )
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Delete a conversation owned by the current user."""
    success = conversation_service.delete_conversation(
        db, conversation_id, current_user["id"]
    )
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"status": "deleted", "conversation_id": conversation_id}


def _is_edit_request(message: str) -> bool:
    edit_keywords = [
        "change", "make", "turn", "convert", "switch", "update",
        "paint", "color", "replace", "add", "remove", "move",
        "walls", "wall", "floor", "ceiling", "furniture", "bed", "sofa",
        "light", "dark", "bright", "warm", "cool", "style", "background",
    ]
    message_lower = message.lower()
    return any(keyword in message_lower for keyword in edit_keywords)


def _is_affirmative(message: str) -> bool:
    text = message.strip().lower()
    affirmatives = {
        "yes", "yeah", "yep", "yup", "ok", "okay", "sure", "please",
        "do it", "do that", "yes do that", "go ahead", "apply it",
        "sounds good", "yes please", "confirm",
    }
    if text in affirmatives:
        return True
    return any(text.startswith(a) for a in ("yes ", "ok ", "sure ", "please "))


def _last_user_edit_request(context_messages: list) -> Optional[str]:
    for msg in reversed(context_messages):
        role = msg.get("role") if isinstance(msg, dict) else getattr(msg, "role", None)
        content = (
            msg.get("content") if isinstance(msg, dict) else getattr(msg, "content", None)
        )
        if role in ("user", MessageRole.USER) and content and _is_edit_request(str(content)):
            if not _is_affirmative(str(content)):
                return str(content)
    return None


def _friendly_image_error(error: Exception) -> str:
    text = str(error)
    if "429" in text or "RESOURCE_EXHAUSTED" in text or "quota" in text.lower():
        return (
            "Gemini image quota exceeded. Enable billing or wait for the free-tier "
            "reset, then try the edit again."
        )
    if "API key" in text or "not set" in text.lower():
        return "Gemini API key is missing or invalid."
    return "the image model failed. Please try again shortly."


def _extract_style_from_prompt(ai_response: str) -> str:
    response_lower = ai_response.lower()
    styles = {
        "modern": ["modern", "contemporary"],
        "minimalist": ["minimalist", "minimal", "simple"],
        "industrial": ["industrial", "factory", "loft"],
        "scandinavian": ["scandinavian", "nordic", "hygge"],
        "bohemian": ["bohemian", "boho", "eclectic"],
        "traditional": ["traditional", "classic", "timeless"],
        "rustic": ["rustic", "farmhouse", "country"],
        "futuristic": ["futuristic", "sci-fi", "high-tech", "future"],
        "mid_century_modern": ["mid-century", "retro", "1950s", "1960s"],
        "coastal": ["coastal", "beach", "nautical"],
        "art_deco": ["art deco", "gatsby", "1920s"],
    }
    for style, keywords in styles.items():
        for keyword in keywords:
            if keyword in response_lower:
                return style
    return "modern"
