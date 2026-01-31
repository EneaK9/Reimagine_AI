"""
ReimagineAI - User Service
Manages user authentication with JSON file persistence
"""
from typing import Optional, Dict
from datetime import datetime
import uuid
import hashlib
import secrets
from .json_storage import json_storage


class UserService:
    """
    User authentication service with JSON file persistence.
    Simple implementation for development - replace with proper auth in production.
    """
    
    def __init__(self):
        print("[UserService] Initialized with JSON storage")
    
    def _hash_password(self, password: str, salt: Optional[str] = None) -> tuple[str, str]:
        """Hash a password with salt."""
        if salt is None:
            salt = secrets.token_hex(16)
        
        # Simple SHA-256 hashing (use bcrypt in production!)
        password_hash = hashlib.sha256(f"{password}{salt}".encode()).hexdigest()
        return password_hash, salt
    
    def _verify_password(self, password: str, stored_hash: str, salt: str) -> bool:
        """Verify a password against stored hash."""
        computed_hash, _ = self._hash_password(password, salt)
        return computed_hash == stored_hash
    
    def _generate_token(self) -> str:
        """Generate a simple auth token."""
        return secrets.token_urlsafe(32)
    
    def signup(self, username: str, email: str, password: str) -> Dict:
        """
        Register a new user.
        Returns user data with token on success.
        Raises ValueError on validation errors.
        """
        # Validate input
        if not username or len(username) < 3:
            raise ValueError("Username must be at least 3 characters")
        
        if not email or '@' not in email:
            raise ValueError("Invalid email address")
        
        if not password or len(password) < 6:
            raise ValueError("Password must be at least 6 characters")
        
        # Check if email already exists
        existing_user = json_storage.get_user_by_email(email)
        if existing_user:
            raise ValueError("Email already registered")
        
        # Check if username already exists
        existing_user = json_storage.get_user_by_username(username)
        if existing_user:
            raise ValueError("Username already taken")
        
        # Create user
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        password_hash, salt = self._hash_password(password)
        token = self._generate_token()
        
        user_data = {
            'id': user_id,
            'username': username,
            'email': email.lower(),
            'password_hash': password_hash,
            'salt': salt,
            'token': token,
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat()
        }
        
        # Save to JSON storage
        json_storage.save_user(user_id, user_data)
        
        print(f"[UserService] New user registered: {username} ({email})")
        
        # Return safe user data (no password hash)
        return {
            'id': user_id,
            'username': username,
            'email': email.lower(),
            'token': token,
            'created_at': user_data['created_at']
        }
    
    def login(self, email: str, password: str) -> Dict:
        """
        Authenticate a user.
        Returns user data with token on success.
        Raises ValueError on auth errors.
        """
        if not email or not password:
            raise ValueError("Email and password are required")
        
        # Find user by email
        user = json_storage.get_user_by_email(email)
        if not user:
            raise ValueError("Invalid email or password")
        
        # Verify password
        if not self._verify_password(password, user['password_hash'], user['salt']):
            raise ValueError("Invalid email or password")
        
        # Generate new token on login
        token = self._generate_token()
        user['token'] = token
        user['updated_at'] = datetime.utcnow().isoformat()
        
        # Update user in storage
        json_storage.save_user(user['id'], user)
        
        print(f"[UserService] User logged in: {user['username']}")
        
        # Return safe user data
        return {
            'id': user['id'],
            'username': user['username'],
            'email': user['email'],
            'token': token,
            'created_at': user['created_at']
        }
    
    def verify_token(self, token: str) -> Optional[Dict]:
        """
        Verify an auth token and return user data.
        Returns None if token is invalid.
        """
        if not token:
            return None
        
        users = json_storage.get_all_users()
        for user in users.values():
            if user.get('token') == token:
                return {
                    'id': user['id'],
                    'username': user['username'],
                    'email': user['email']
                }
        
        return None
    
    def get_user(self, user_id: str) -> Optional[Dict]:
        """Get user by ID (safe data only)."""
        user = json_storage.get_user_by_id(user_id)
        if user:
            return {
                'id': user['id'],
                'username': user['username'],
                'email': user['email'],
                'created_at': user['created_at']
            }
        return None
    
    def update_password(self, user_id: str, old_password: str, new_password: str) -> bool:
        """Update user password."""
        user = json_storage.get_user_by_id(user_id)
        if not user:
            raise ValueError("User not found")
        
        # Verify old password
        if not self._verify_password(old_password, user['password_hash'], user['salt']):
            raise ValueError("Current password is incorrect")
        
        if len(new_password) < 6:
            raise ValueError("New password must be at least 6 characters")
        
        # Hash new password
        password_hash, salt = self._hash_password(new_password)
        user['password_hash'] = password_hash
        user['salt'] = salt
        user['updated_at'] = datetime.utcnow().isoformat()
        
        # Save updated user
        json_storage.save_user(user_id, user)
        
        return True
    
    def logout(self, user_id: str) -> bool:
        """Logout user by invalidating token."""
        user = json_storage.get_user_by_id(user_id)
        if user:
            user['token'] = None
            user['updated_at'] = datetime.utcnow().isoformat()
            json_storage.save_user(user_id, user)
            return True
        return False


# Singleton instance
user_service = UserService()
