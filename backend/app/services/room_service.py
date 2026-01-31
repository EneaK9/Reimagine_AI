"""
ReimagineAI - Room Service
Handles 3D room model storage and management
"""
import os
import json
import uuid
from datetime import datetime
from typing import Optional, Dict, List, Any
from fastapi import UploadFile
import aiofiles

from ..config import get_settings

settings = get_settings()


class RoomService:
    """
    Service for managing scanned 3D room models
    """
    
    def __init__(self):
        # Storage paths
        self.data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data')
        self.rooms_dir = os.path.join(self.data_dir, 'rooms')
        self.rooms_index_path = os.path.join(self.data_dir, 'rooms.json')
        
        # Ensure directories exist
        os.makedirs(self.rooms_dir, exist_ok=True)
        
        # Load rooms index
        self._rooms: Dict[str, Dict[str, Any]] = {}
        self._load_rooms_index()
    
    def _load_rooms_index(self) -> None:
        """Load rooms index from JSON file"""
        if os.path.exists(self.rooms_index_path):
            try:
                with open(self.rooms_index_path, 'r') as f:
                    data = json.load(f)
                    self._rooms = data.get('rooms', {})
                print(f"[RoomService] Loaded {len(self._rooms)} rooms from index")
            except Exception as e:
                print(f"[RoomService] Error loading rooms index: {e}")
                self._rooms = {}
        else:
            self._rooms = {}
    
    def _save_rooms_index(self) -> None:
        """Save rooms index to JSON file"""
        try:
            with open(self.rooms_index_path, 'w') as f:
                json.dump({'rooms': self._rooms}, f, indent=2)
        except Exception as e:
            print(f"[RoomService] Error saving rooms index: {e}")
    
    async def save_room(self, file: UploadFile, name: str) -> Dict[str, Any]:
        """
        Save an uploaded room model file
        
        Args:
            file: The uploaded file
            name: Name for the room
            
        Returns:
            Room metadata dict
        """
        # Generate room ID
        room_id = f"room_{uuid.uuid4().hex[:12]}"
        
        # Determine file extension
        original_ext = os.path.splitext(file.filename)[1].lower() if file.filename else '.glb'
        
        # Save file
        file_name = f"{room_id}{original_ext}"
        file_path = os.path.join(self.rooms_dir, file_name)
        
        async with aiofiles.open(file_path, 'wb') as f:
            content = await file.read()
            await f.write(content)
        
        # Get file size
        file_size = os.path.getsize(file_path)
        
        # Create room metadata
        now = datetime.utcnow().isoformat()
        room_data = {
            'id': room_id,
            'name': name,
            'file_path': file_path,
            'file_name': file_name,
            'file_size': file_size,
            'file_type': original_ext,
            'created_at': now,
            'updated_at': now,
            'metadata': {
                'original_filename': file.filename,
                'file_size_bytes': file_size,
            }
        }
        
        # Save to index
        self._rooms[room_id] = room_data
        self._save_rooms_index()
        
        print(f"[RoomService] Saved room {room_id}: {file_path} ({file_size} bytes)")
        
        return room_data
    
    async def get_room(self, room_id: str) -> Optional[Dict[str, Any]]:
        """
        Get room metadata by ID
        
        Args:
            room_id: The room ID
            
        Returns:
            Room metadata or None if not found
        """
        return self._rooms.get(room_id)
    
    async def list_rooms(self) -> List[Dict[str, Any]]:
        """
        List all rooms
        
        Returns:
            List of room metadata dicts
        """
        rooms = list(self._rooms.values())
        # Sort by created_at descending
        rooms.sort(key=lambda r: r.get('created_at', ''), reverse=True)
        return rooms
    
    async def delete_room(self, room_id: str) -> bool:
        """
        Delete a room and its file
        
        Args:
            room_id: The room ID
            
        Returns:
            True if deleted, False if not found
        """
        room = self._rooms.get(room_id)
        
        if not room:
            return False
        
        # Delete file
        file_path = room.get('file_path')
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
                print(f"[RoomService] Deleted file: {file_path}")
            except Exception as e:
                print(f"[RoomService] Error deleting file: {e}")
        
        # Remove from index
        del self._rooms[room_id]
        self._save_rooms_index()
        
        print(f"[RoomService] Deleted room {room_id}")
        return True
    
    async def update_room_metadata(self, room_id: str, metadata: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Update room metadata
        
        Args:
            room_id: The room ID
            metadata: Metadata to update
            
        Returns:
            Updated room data or None if not found
        """
        room = self._rooms.get(room_id)
        
        if not room:
            return None
        
        # Update metadata
        room['metadata'] = {**room.get('metadata', {}), **metadata}
        room['updated_at'] = datetime.utcnow().isoformat()
        
        self._save_rooms_index()
        
        return room


# Singleton instance
room_service = RoomService()
