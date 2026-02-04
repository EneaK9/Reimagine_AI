"""
ReimagineAI - Conversation Service
Manages chat conversations and history with JSON file persistence
"""
from typing import Dict, List, Optional
from datetime import datetime
import uuid
from ..models.schemas import ChatMessage, Conversation, MessageRole
from .json_storage import json_storage


class ConversationService:
    """
    Conversation storage with JSON file persistence.
    Data is saved to local JSON files for development.
    """
    
    def __init__(self):
        # Load existing conversations from JSON storage
        self._load_conversations()
        print(f"[ConversationService] Loaded {len(self._conversations)} conversations from storage")
    
    def _load_conversations(self) -> None:
        """Load conversations from JSON storage into memory."""
        self._conversations: Dict[str, Conversation] = {}
        
        stored_convs = json_storage.get_all_conversations()
        for conv_id, conv_data in stored_convs.items():
            try:
                # Parse messages
                messages = []
                for msg_data in conv_data.get('messages', []):
                    messages.append(ChatMessage(
                        role=MessageRole(msg_data['role']),
                        content=msg_data['content'],
                        image_url=msg_data.get('image_url'),
                        timestamp=datetime.fromisoformat(msg_data['timestamp']) if msg_data.get('timestamp') else datetime.utcnow()
                    ))
                
                # Create conversation object
                conversation = Conversation(
                    id=conv_data['id'],
                    title=conv_data['title'],
                    messages=messages,
                    created_at=datetime.fromisoformat(conv_data['created_at']) if conv_data.get('created_at') else datetime.utcnow(),
                    updated_at=datetime.fromisoformat(conv_data['updated_at']) if conv_data.get('updated_at') else datetime.utcnow(),
                    original_image=conv_data.get('original_image'),
                    last_generated_image=conv_data.get('last_generated_image'),
                    mesh_id=conv_data.get('mesh_id')
                )
                self._conversations[conv_id] = conversation
            except Exception as e:
                print(f"[ConversationService] Error loading conversation {conv_id}: {e}")
    
    def _save_conversation(self, conversation: Conversation) -> None:
        """Save a conversation to JSON storage."""
        conv_data = {
            'id': conversation.id,
            'title': conversation.title,
            'messages': [
                {
                    'role': msg.role.value,
                    'content': msg.content,
                    'image_url': msg.image_url,
                    'timestamp': msg.timestamp.isoformat() if msg.timestamp else None
                }
                for msg in conversation.messages
            ],
            'created_at': conversation.created_at.isoformat(),
            'updated_at': conversation.updated_at.isoformat(),
            'original_image': getattr(conversation, 'original_image', None),
            'last_generated_image': getattr(conversation, 'last_generated_image', None),
            'mesh_id': getattr(conversation, 'mesh_id', None)
        }
        json_storage.save_conversation(conversation.id, conv_data)
    
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
        self._save_conversation(conversation)
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
        
        # Save to JSON storage
        self._save_conversation(conversation)
        
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
            json_storage.delete_conversation(conversation_id)
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
            
            # Attach images to the last assistant message
            if image_urls and conversation.messages:
                # Find the last assistant message and create updated list
                new_messages = []
                found_assistant = False
                
                # Go through messages in reverse to find last assistant
                for i in range(len(conversation.messages) - 1, -1, -1):
                    msg = conversation.messages[i]
                    if msg.role == MessageRole.ASSISTANT and not found_assistant:
                        # Create new message with image URLs (use ||| separator - commas exist in base64!)
                        new_messages.insert(0, ChatMessage(
                            role=msg.role,
                            content=msg.content,
                            image_url="|||".join(image_urls),
                            timestamp=msg.timestamp
                        ))
                        found_assistant = True
                        print(f"[ConversationService] Attached {len(image_urls)} images to assistant message")
                    else:
                        new_messages.insert(0, msg)
                
                # Replace the messages list
                conversation.messages = new_messages
            
            # Save to JSON storage
            self._save_conversation(conversation)
            print(f"[ConversationService] Saved conversation with images")
    
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
            self._save_conversation(conversation)
    
    def store_mesh_reference(self, conversation_id: str, mesh_id: str) -> None:
        """Store the mesh ID associated with this conversation."""
        conversation = self._conversations.get(conversation_id)
        if conversation:
            conversation.mesh_id = mesh_id
            self._save_conversation(conversation)
            print(f"[ConversationService] Stored mesh {mesh_id} for conversation {conversation_id}")
    
    def get_mesh_id(self, conversation_id: str) -> Optional[str]:
        """Get the mesh ID associated with a conversation."""
        conversation = self._conversations.get(conversation_id)
        if conversation:
            return getattr(conversation, 'mesh_id', None)
        return None
    
    def has_mesh(self, conversation_id: str) -> bool:
        """Check if a conversation has an associated mesh."""
        return self.get_mesh_id(conversation_id) is not None


# Singleton instance
conversation_service = ConversationService()
