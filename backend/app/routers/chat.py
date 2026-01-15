"""
ReimagineAI - Chat Router
Handles all chat-related endpoints
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from typing import Optional
import base64

from ..models.schemas import (
    ChatRequest,
    ChatResponse,
    MessageRole,
    ConversationSummary
)
from ..services.openai_service import openai_service
from ..services.conversation_service import conversation_service
from ..services.gemini_service import gemini_service

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post("/", response_model=ChatResponse)
async def send_message(request: ChatRequest):
    """
    Send a message to the AI assistant.
    Optionally include an image (base64 encoded) for room analysis.
    Supports follow-up edits on previously generated images.
    """
    try:
        # Get or create conversation
        conversation = conversation_service.get_or_create_conversation(
            request.conversation_id
        )
        
        # Determine which image to use for editing
        image_to_edit = None
        is_follow_up = False
        
        if request.image_base64:
            # User uploaded a new image - store it as original
            image_to_edit = request.image_base64
            conversation_service.store_original_image(conversation.id, request.image_base64)
        else:
            # No new image - check if we have a previous generated image to edit
            last_image = conversation_service.get_last_generated_image(conversation.id)
            if last_image:
                image_to_edit = last_image
                is_follow_up = True
                print(f"Using last generated image for follow-up edit")
        
        # Add user message to conversation
        conversation_service.add_message(
            conversation.id,
            MessageRole.USER,
            request.message,
            image_url="[image attached]" if request.image_base64 else ("[editing previous image]" if is_follow_up else None)
        )
        
        # Get conversation context for AI
        context_messages = conversation_service.get_messages_for_context(
            conversation.id
        )
        
        # Get AI response
        ai_response = await openai_service.chat_completion(
            messages=context_messages,
            image_base64=request.image_base64  # Only pass new images for analysis
        )
        
        # Check if we should generate/edit images
        generated_images = []
        image_prompt = openai_service.extract_image_prompt(ai_response)
        
        # Generate images if we have an image to edit AND user is requesting changes
        if image_to_edit and (image_prompt or _is_edit_request(request.message)):
            try:
                style = _extract_style_from_prompt(ai_response)
                
                # Use the user's EXACT request for precise edits
                edit_instruction = request.message
                
                generated_images = await gemini_service.edit_room(
                    image_base64=image_to_edit,
                    edit_instruction=edit_instruction,
                    style=style,
                )
                
                # Store the last generated image for future follow-ups
                if generated_images:
                    # Extract base64 from data URL for storage
                    last_img = generated_images[0]
                    if last_img.startswith('data:'):
                        last_img_base64 = last_img.split(',')[1]
                    else:
                        last_img_base64 = last_img
                    
                    conversation_service.update_conversation_with_images(
                        conversation.id,
                        generated_images,
                        last_image_base64=last_img_base64
                    )
                    
            except Exception as img_error:
                print(f"Image generation failed: {img_error}")
                import traceback
                traceback.print_exc()
        
        # Add AI response to conversation
        conversation_service.add_message(
            conversation.id,
            MessageRole.ASSISTANT,
            ai_response
        )
        
        return ChatResponse(
            conversation_id=conversation.id,
            message=ai_response,
            generated_images=generated_images,
            furniture_suggestions=[]  # TODO: Implement furniture matching
        )
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


def _is_edit_request(message: str) -> bool:
    """Check if the message is requesting an edit to the room."""
    edit_keywords = [
        "change", "make", "turn", "convert", "switch", "update",
        "paint", "color", "replace", "add", "remove", "move",
        "walls", "floor", "ceiling", "furniture", "bed", "sofa",
        "light", "dark", "bright", "warm", "cool", "style"
    ]
    message_lower = message.lower()
    return any(keyword in message_lower for keyword in edit_keywords)


@router.post("/with-image", response_model=ChatResponse)
async def send_message_with_image(
    message: str = Form(...),
    conversation_id: Optional[str] = Form(None),
    image: UploadFile = File(...)
):
    """
    Send a message with an uploaded image file.
    Alternative to base64 encoding in the request body.
    """
    try:
        # Read and encode image
        image_content = await image.read()
        image_base64 = base64.b64encode(image_content).decode('utf-8')
        
        # Create request and delegate to main handler
        request = ChatRequest(
            message=message,
            conversation_id=conversation_id,
            image_base64=image_base64
        )
        
        return await send_message(request)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversations")
async def list_conversations():
    """
    Get all conversations for the current user.
    """
    conversations = conversation_service.list_conversations()
    return [
        ConversationSummary(
            id=conv.id,
            title=conv.title,
            last_message=conv.messages[-1].content if conv.messages else None,
            image_count=len([m for m in conv.messages if m.image_url]),
            created_at=conv.created_at,
            updated_at=conv.updated_at
        )
        for conv in conversations
    ]


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """
    Get a specific conversation with all messages.
    """
    conversation = conversation_service.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """
    Delete a conversation.
    """
    success = conversation_service.delete_conversation(conversation_id)
    if not success:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"status": "deleted", "conversation_id": conversation_id}


def _extract_style_from_prompt(ai_response: str) -> str:
    """
    Extract design style from AI response.
    Looks for style keywords in the response.
    """
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
    
    return "modern"  # Default style
