"""
ReimagineAI - Chat Router
Handles all chat-related endpoints (PostgreSQL-backed, user-scoped).
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from typing import Optional
import asyncio
import base64
import re

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
from ..services.semantic_service import semantic_service
from ..db.session import get_db
from ..deps import check_base64_size, get_current_user, read_upload_limited

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

    if request.scene_id:
        # Link a 3D room the user built (e.g. from the scan screen) to this chat,
        # only if it is theirs.
        from ..services.scene_service import scene_service

        if scene_service.get_scene(db, request.scene_id, user_id):
            conversation_service.store_scene_reference(
                db, conversation.id, request.scene_id, user_id=user_id
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

    scene_id = conversation_service.get_scene_id(db, conversation.id, user_id=user_id)

    # What does the user want? A typed judgment (TypeSafe, ~0.3 s) when
    # configured, keyword rules otherwise — asked alongside the chat reply.
    previous_assistant = next(
        (m.get("content") for m in reversed(context_messages[:-1])
         if isinstance(m, dict) and m.get("role") in ("assistant", MessageRole.ASSISTANT)),
        None,
    )
    ai_response, route = await asyncio.gather(
        openai_service.chat_completion(
            messages=context_messages,
            image_base64=request.image_base64,
        ),
        semantic_service.route_chat(
            request.message,
            previous_assistant if isinstance(previous_assistant, str) else None,
            has_photo=image_to_edit is not None,
            has_scene=bool(scene_id),
        ),
    )
    confident = route is not None and route.intent_confidence >= 0.6
    is_confirmation = (
        route.intent == "confirm_suggestion" if confident else _is_affirmative(request.message)
    )

    generated_images = []
    image_error_note = None
    image_prompt = openai_service.extract_image_prompt(ai_response)
    if confident:
        # A plain question shouldn't trigger (and pay for) an image edit even
        # when the assistant sketched an image prompt.
        wants_edit = route.intent == "change_room" or (is_follow_up and is_confirmation)
    else:
        wants_edit = (
            image_prompt
            or _is_edit_request(request.message)
            or (is_follow_up and is_confirmation)
        )

    if image_to_edit and wants_edit:
        try:
            style = _extract_style_from_prompt(ai_response)
            edit_instruction = request.message
            if is_confirmation and image_prompt:
                edit_instruction = image_prompt
            elif is_confirmation:
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

    # Notes go after the visible reply, never after the [IMAGE_PROMPT] block
    # (which is cut off before the reply is shown).
    reply, _, prompt_block = ai_response.partition("[IMAGE_PROMPT]")
    reply = reply.strip()
    notes: list[str] = []
    if image_error_note:
        notes.append(f"⚠️ {image_error_note}")

    # If this conversation has an editable 3D scene, mirror the edit onto it
    scene_updated = False
    scene_instruction = None
    from_proposal = False
    if scene_id:
        if confident:
            if route.intent == "change_room" and route.scene_edit >= 0.5:
                scene_instruction = request.message
            elif route.intent == "confirm_suggestion":
                # "yes, do it" applies what the assistant just proposed. Only
                # on a confident judgment: keyword rules can't tell "ok
                # thanks" from a confirmation.
                proposal = (previous_assistant or "").partition("[IMAGE_PROMPT]")[0].strip()
                if proposal:
                    scene_instruction = f"Apply the change proposed here: {proposal}"
                    from_proposal = True
        elif _is_edit_request(request.message) and not is_confirmation:
            scene_instruction = request.message
    if scene_instruction:
        try:
            from ..services.scene_service import scene_service

            # A proposal also names the current colors ("your light grey walls
            # could be navy"): only the full parser reads that correctly
            _, applied_ops, scene_message = await scene_service.nl_edit(
                db, scene_id, scene_instruction, user_id=user_id, fast_paths=not from_proposal
            )
            if applied_ops:
                scene_updated = True
                notes.append(f"🛋️ {scene_message}")
        except Exception as scene_error:
            print(f"[Chat] Scene edit failed: {scene_error}")

    clean_response = "\n\n".join([reply, *notes]) if notes else reply
    stored = clean_response + (f"\n\n[IMAGE_PROMPT]{prompt_block}" if prompt_block else "")
    conversation_service.add_message(
        db,
        conversation.id,
        MessageRole.ASSISTANT,
        stored,
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

    return ChatResponse(
        conversation_id=conversation.id,
        message=clean_response,
        generated_images=generated_images,
        furniture_suggestions=[],
        mesh_url=mesh_url,
        mesh_id=mesh_id,
        scene_id=scene_id,
        scene_updated=scene_updated,
    )


@router.post("/", response_model=ChatResponse)
async def send_message(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Send a message to the AI assistant (requires auth)."""
    check_base64_size(request.image_base64)
    try:
        return await _handle_chat(request, db, current_user)
    except HTTPException:
        raise
    except Exception:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Chat failed. Please try again.")


@router.post("/with-image", response_model=ChatResponse)
async def send_message_with_image(
    message: str = Form(...),
    conversation_id: Optional[str] = Form(None),
    mesh_id: Optional[str] = Form(None),
    scene_id: Optional[str] = Form(None),
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Send a message with an uploaded image file (requires auth)."""
    image_content = await read_upload_limited(image)
    try:
        image_base64 = base64.b64encode(image_content).decode("utf-8")
        request = ChatRequest(
            message=message,
            conversation_id=conversation_id,
            image_base64=image_base64,
            mesh_id=mesh_id,
            scene_id=scene_id,
        )
        return await _handle_chat(request, db, current_user)
    except HTTPException:
        raise
    except Exception:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Chat failed. Please try again.")


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


_EDIT_WORDS = re.compile(
    r"\b(change|make|turn|convert|switch|update|paint|colou?r|recolou?r|replace|add|"
    r"remove|delete|move|rotate|swap|walls?|floors?|ceiling|furniture|beds?|sofas?|"
    r"couch|lighter|darker|brighter|warmer|cooler|style)\b"
)


def _is_edit_request(message: str) -> bool:
    """Keyword fallback when no typed judgment is available (whole words
    only: "bedroom" is not "bed", "address" is not "add")."""
    return bool(_EDIT_WORDS.search(message.lower()))


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
