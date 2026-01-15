"""
ReimagineAI - Conversation Service
Manages chat conversations and history
"""
from typing import Dict, List, Optional
from datetime import datetime
import uuid
from ..models.schemas import ChatMessage, Conversation, MessageRole


class ConversationService:
    """
    In-memory conversation storage for MVP.
    TODO: Replace with database storage in production.
    """
    
    def __init__(self):
        # In-memory storage: {conversation_id: Conversation}
        self._conversations: Dict[str, Conversation] = {}
    
    def create_conversation(self, title: str = "New Chat") -> Conversation:
        """Create a new conversation."""
        conversation_id = f"conv_{uuid.uuid4().hex[:12]}"
        conversation = Conversation(
            id=conversation_id,
            title=title,
            messages=[],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        self._conversations[conversation_id] = conversation
        return conversation
    
    def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """Get a conversation by ID."""
        return self._conversations.get(conversation_id)
    
    def get_or_create_conversation(self, conversation_id: Optional[str]) -> Conversation:
        """Get existing conversation or create a new one."""
        if conversation_id and conversation_id in self._conversations:
            return self._conversations[conversation_id]
        return self.create_conversation()
    
    def add_message(
        self,
        conversation_id: str,
        role: MessageRole,
        content: str,
        image_url: Optional[str] = None
    ) -> ChatMessage:
        """Add a message to a conversation."""
        conversation = self._conversations.get(conversation_id)
        if not conversation:
            raise ValueError(f"Conversation {conversation_id} not found")
        
        message = ChatMessage(
            role=role,
            content=content,
            image_url=image_url,
            timestamp=datetime.utcnow()
        )
        conversation.messages.append(message)
        conversation.updated_at = datetime.utcnow()
        
        # Update title based on first user message
        if len(conversation.messages) == 1 and role == MessageRole.USER:
            conversation.title = content[:50] + ("..." if len(content) > 50 else "")
        
        return message
    
    def get_messages_for_context(
        self,
        conversation_id: str,
        max_messages: int = 10
    ) -> List[Dict]:
        """
        Get recent messages formatted for OpenAI API.
        Limits to last N messages to manage context window.
        """
        conversation = self._conversations.get(conversation_id)
        if not conversation:
            return []
        
        # Get last N messages
        recent_messages = conversation.messages[-max_messages:]
        
        return [
            {
                "role": msg.role.value,
                "content": msg.content,
                "image_url": msg.image_url
            }
            for msg in recent_messages
        ]
    
    def list_conversations(self, limit: int = 20) -> List[Conversation]:
        """List all conversations, most recent first."""
        conversations = list(self._conversations.values())
        conversations.sort(key=lambda x: x.updated_at, reverse=True)
        return conversations[:limit]
    
    def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation."""
        if conversation_id in self._conversations:
            del self._conversations[conversation_id]
            return True
        return False
    
    def update_conversation_with_images(
        self,
        conversation_id: str,
        image_urls: List[str],
        last_image_base64: Optional[str] = None
    ) -> None:
        """Store generated image URLs and last image in the conversation context."""
        conversation = self._conversations.get(conversation_id)
        if conversation:
            # Store the last generated image for follow-up edits
            if last_image_base64:
                conversation.last_generated_image = last_image_base64
            
            # Add a system message noting the generated images
            if image_urls:
                note = f"[Generated {len(image_urls)} design variations]"
                self.add_message(
                    conversation_id,
                    MessageRole.SYSTEM,
                    note
                )
    
    def get_last_generated_image(self, conversation_id: str) -> Optional[str]:
        """Get the last generated image base64 for follow-up edits."""
        conversation = self._conversations.get(conversation_id)
        if conversation:
            return getattr(conversation, 'last_generated_image', None)
        return None
    
    def store_original_image(self, conversation_id: str, image_base64: str) -> None:
        """Store the original uploaded image for reference."""
        conversation = self._conversations.get(conversation_id)
        if conversation:
            conversation.original_image = image_base64


# Singleton instance
conversation_service = ConversationService()
