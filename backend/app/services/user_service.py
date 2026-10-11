"""
ReimagineAI - User Service (PostgreSQL)

Passwords are stored as PBKDF2-HMAC-SHA256 in a self-describing string:
    pbkdf2_sha256$<iterations>$<salt_b64>$<hash_b64>
Legacy rows (one round of SHA-256 over password + hex salt, hex digest in
password_hash, salt in its own column) still verify and are re-hashed to the
new format on the next successful login.
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, Optional
import base64
import binascii
import hashlib
import hmac
import secrets
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import User

PBKDF2_ALGORITHM = "pbkdf2_sha256"
PBKDF2_ITERATIONS = 600_000  # OWASP (2023) guidance for PBKDF2-HMAC-SHA256
PBKDF2_SALT_BYTES = 16


class UserService:
    """User authentication persisted in PostgreSQL."""

    def _hash_password(self, password: str) -> tuple[str, str]:
        """
        Hash a password with PBKDF2-HMAC-SHA256.
        Returns (encoded hash for users.password_hash, salt for users.salt).
        The salt is embedded in the encoded hash; the column copy only keeps
        the NOT NULL salt column populated.
        """
        salt = secrets.token_bytes(PBKDF2_SALT_BYTES)
        derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
        salt_b64 = base64.b64encode(salt).decode("ascii")
        hash_b64 = base64.b64encode(derived).decode("ascii")
        return f"{PBKDF2_ALGORITHM}${PBKDF2_ITERATIONS}${salt_b64}${hash_b64}", salt_b64

    def _verify_password(self, password: str, stored_hash: str, salt: Optional[str]) -> bool:
        """Constant-time check against a PBKDF2 hash or a legacy salted SHA-256 hash."""
        if not stored_hash:
            return False
        if stored_hash.startswith(f"{PBKDF2_ALGORITHM}$"):
            try:
                _, iterations, salt_b64, hash_b64 = stored_hash.split("$")
                rounds = int(iterations)
                salt_bytes = base64.b64decode(salt_b64, validate=True)
                expected = base64.b64decode(hash_b64, validate=True)
            except (ValueError, binascii.Error):
                print("[UserService] Malformed PBKDF2 password hash")
                return False
            if rounds < 1 or not expected:
                return False
            derived = hashlib.pbkdf2_hmac(
                "sha256", password.encode("utf-8"), salt_bytes, rounds, dklen=len(expected)
            )
            return hmac.compare_digest(derived, expected)
        # Legacy: sha256(password + salt) as a hex digest
        legacy = hashlib.sha256(f"{password}{salt or ''}".encode()).hexdigest()
        return hmac.compare_digest(legacy.encode(), stored_hash.encode())

    def _needs_rehash(self, stored_hash: str) -> bool:
        """True for legacy hashes or PBKDF2 hashes below the current iteration count."""
        parts = (stored_hash or "").split("$")
        if len(parts) != 4 or parts[0] != PBKDF2_ALGORITHM:
            return True
        try:
            return int(parts[1]) < PBKDF2_ITERATIONS
        except ValueError:
            return True

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

        if self._needs_rehash(user.password_hash):
            # Transparent upgrade (legacy SHA-256 or fewer iterations);
            # persisted by the commit below together with the new token.
            user.password_hash, user.salt = self._hash_password(password)
            print(f"[UserService] Upgraded password hash for {user.username}")

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
