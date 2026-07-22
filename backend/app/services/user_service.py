"""
ReimagineAI - User Service (PostgreSQL)
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, Optional
import hashlib
import secrets
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import User


class UserService:
    """User authentication persisted in PostgreSQL."""

    def _hash_password(self, password: str, salt: Optional[str] = None) -> tuple[str, str]:
        if salt is None:
            salt = secrets.token_hex(16)
        password_hash = hashlib.sha256(f"{password}{salt}".encode()).hexdigest()
        return password_hash, salt

    def _verify_password(self, password: str, stored_hash: str, salt: str) -> bool:
        computed_hash, _ = self._hash_password(password, salt)
        return secrets.compare_digest(computed_hash, stored_hash)

    def _generate_token(self) -> str:
        return secrets.token_urlsafe(32)

    def _public_user(self, user: User, include_token: bool = False) -> Dict:
        data = {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        }
        if include_token:
            data["token"] = user.token
        return data

    def signup(self, db: Session, username: str, email: str, password: str) -> Dict:
        if not username or len(username) < 3:
            raise ValueError("Username must be at least 3 characters")
        if not email or "@" not in email:
            raise ValueError("Invalid email address")
        if not password or len(password) < 6:
            raise ValueError("Password must be at least 6 characters")

        email_norm = email.lower().strip()
        if db.scalar(select(User).where(User.email == email_norm)):
            raise ValueError("Email already registered")
        if db.scalar(select(User).where(User.username == username)):
            raise ValueError("Username already taken")

        password_hash, salt = self._hash_password(password)
        user = User(
            id=f"user_{uuid.uuid4().hex[:12]}",
            username=username,
            email=email_norm,
            password_hash=password_hash,
            salt=salt,
            token=self._generate_token(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        print(f"[UserService] New user registered: {username} ({email_norm})")
        return self._public_user(user, include_token=True)

    def login(self, db: Session, email: str, password: str) -> Dict:
        if not email or not password:
            raise ValueError("Email and password are required")

        user = db.scalar(select(User).where(User.email == email.lower().strip()))
        if not user or not self._verify_password(password, user.password_hash, user.salt):
            raise ValueError("Invalid email or password")

        user.token = self._generate_token()
        user.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(user)
        print(f"[UserService] User logged in: {user.username}")
        return self._public_user(user, include_token=True)

    def verify_token(self, db: Session, token: str) -> Optional[Dict]:
        if not token:
            return None
        user = db.scalar(select(User).where(User.token == token))
        if not user:
            return None
        return {"id": user.id, "username": user.username, "email": user.email}

    def get_user(self, db: Session, user_id: str) -> Optional[Dict]:
        user = db.get(User, user_id)
        if not user:
            return None
        return self._public_user(user)

    def update_password(
        self, db: Session, user_id: str, old_password: str, new_password: str
    ) -> bool:
        user = db.get(User, user_id)
        if not user:
            raise ValueError("User not found")
        if not self._verify_password(old_password, user.password_hash, user.salt):
            raise ValueError("Current password is incorrect")
        if len(new_password) < 6:
            raise ValueError("New password must be at least 6 characters")

        password_hash, salt = self._hash_password(new_password)
        user.password_hash = password_hash
        user.salt = salt
        user.updated_at = datetime.utcnow()
        db.commit()
        return True

    def logout(self, db: Session, user_id: str) -> bool:
        user = db.get(User, user_id)
        if not user:
            return False
        user.token = None
        user.updated_at = datetime.utcnow()
        db.commit()
        return True


user_service = UserService()
