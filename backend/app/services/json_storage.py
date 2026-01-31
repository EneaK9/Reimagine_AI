"""
ReimagineAI - JSON Storage Service
Local file-based storage for development (before database setup)
"""
import json
import os
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path


class JSONStorage:
    """
    Simple JSON file storage for local development.
    Stores data in JSON files in a 'data' directory.
    """
    
    def __init__(self, data_dir: str = "data"):
        # Create data directory relative to backend folder
        self.data_dir = Path(__file__).parent.parent.parent / data_dir
        self.data_dir.mkdir(exist_ok=True)
        
        # Initialize storage files
        self.conversations_file = self.data_dir / "conversations.json"
        self.users_file = self.data_dir / "users.json"
        
        # Initialize files if they don't exist
        self._init_file(self.conversations_file, {})
        self._init_file(self.users_file, {})
        
        print(f"[Storage] JSON storage initialized at: {self.data_dir}")
    
    def _init_file(self, filepath: Path, default_data: Any) -> None:
        """Initialize a JSON file if it doesn't exist."""
        if not filepath.exists():
            self._write_json(filepath, default_data)
    
    def _read_json(self, filepath: Path) -> Any:
        """Read data from a JSON file."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}
    
    def _write_json(self, filepath: Path, data: Any) -> None:
        """Write data to a JSON file."""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=self._json_serializer)
    
    def _json_serializer(self, obj: Any) -> Any:
        """Custom JSON serializer for datetime objects."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
    
    # ============ Conversations ============
    
    def get_all_conversations(self) -> Dict[str, Any]:
        """Get all conversations."""
        return self._read_json(self.conversations_file)
    
    def get_conversation(self, conversation_id: str) -> Optional[Dict]:
        """Get a specific conversation."""
        conversations = self.get_all_conversations()
        return conversations.get(conversation_id)
    
    def save_conversation(self, conversation_id: str, conversation_data: Dict) -> None:
        """Save or update a conversation."""
        conversations = self.get_all_conversations()
        conversations[conversation_id] = conversation_data
        self._write_json(self.conversations_file, conversations)
    
    def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation."""
        conversations = self.get_all_conversations()
        if conversation_id in conversations:
            del conversations[conversation_id]
            self._write_json(self.conversations_file, conversations)
            return True
        return False
    
    def list_conversations(self, limit: int = 20) -> List[Dict]:
        """List conversations sorted by updated_at."""
        conversations = self.get_all_conversations()
        conv_list = list(conversations.values())
        
        # Sort by updated_at descending
        conv_list.sort(
            key=lambda x: x.get('updated_at', ''),
            reverse=True
        )
        
        return conv_list[:limit]
    
    # ============ Users ============
    
    def get_all_users(self) -> Dict[str, Any]:
        """Get all users."""
        return self._read_json(self.users_file)
    
    def get_user_by_id(self, user_id: str) -> Optional[Dict]:
        """Get a user by ID."""
        users = self.get_all_users()
        return users.get(user_id)
    
    def get_user_by_email(self, email: str) -> Optional[Dict]:
        """Get a user by email."""
        users = self.get_all_users()
        for user in users.values():
            if user.get('email', '').lower() == email.lower():
                return user
        return None
    
    def get_user_by_username(self, username: str) -> Optional[Dict]:
        """Get a user by username."""
        users = self.get_all_users()
        for user in users.values():
            if user.get('username', '').lower() == username.lower():
                return user
        return None
    
    def save_user(self, user_id: str, user_data: Dict) -> None:
        """Save or update a user."""
        users = self.get_all_users()
        users[user_id] = user_data
        self._write_json(self.users_file, users)
    
    def delete_user(self, user_id: str) -> bool:
        """Delete a user."""
        users = self.get_all_users()
        if user_id in users:
            del users[user_id]
            self._write_json(self.users_file, users)
            return True
        return False


# Singleton instance
json_storage = JSONStorage()
