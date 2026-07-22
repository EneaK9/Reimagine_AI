"""
ReimagineAI - Conversation Service (PostgreSQL)
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional
import uuid

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, selectinload

from ..db.models import Conversation as ConversationRow
from ..db.models import Message as MessageRow
from ..models.schemas import ChatMessage, Conversation, MessageRole


class ConversationService:
    """Conversation + message persistence in PostgreSQL."""

    def _to_schema(self, row: ConversationRow) -> Conversation:
        messages = [
            ChatMessage(
                role=MessageRole(msg.role),
                content=msg.content or "",
                image_url=msg.image_url,
                timestamp=msg.created_at or datetime.utcnow(),
            )
            for msg in (row.messages or [])
        ]
        return Conversation(
            id=row.id,
            title=row.title,
            messages=messages,
            created_at=row.created_at,
            updated_at=row.updated_at,
            original_image=row.original_image,
            last_generated_image=row.last_generated_image,
            mesh_id=row.mesh_id,
        )

    def _get_row(
        self,
        db: Session,
        conversation_id: str,
        user_id: Optional[str] = None,
        *,
        with_messages: bool = True,
    ) -> Optional[ConversationRow]:
        stmt = select(ConversationRow).where(ConversationRow.id == conversation_id)
        if user_id:
            stmt = stmt.where(ConversationRow.user_id == user_id)
        if with_messages:
            stmt = stmt.options(selectinload(ConversationRow.messages))
        return db.scalar(stmt)

    def create_conversation(
        self, db: Session, user_id: str, title: str = "New Chat"
    ) -> Conversation:
        row = ConversationRow(
            id=f"conv_{uuid.uuid4().hex[:12]}",
            user_id=user_id,
            title=title,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        row.messages = []
        return self._to_schema(row)

    def get_conversation(
        self, db: Session, conversation_id: str, user_id: Optional[str] = None
    ) -> Optional[Conversation]:
        row = self._get_row(db, conversation_id, user_id)
        return self._to_schema(row) if row else None

    def get_or_create_conversation(
        self,
        db: Session,
        user_id: str,
        conversation_id: Optional[str],
    ) -> Conversation:
        if conversation_id:
            existing = self.get_conversation(db, conversation_id, user_id)
            if existing:
                return existing
        return self.create_conversation(db, user_id)

    def add_message(
        self,
        db: Session,
        conversation_id: str,
        role: MessageRole,
        content: str,
        image_url: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> ChatMessage:
        row = self._get_row(db, conversation_id, user_id)
        if not row:
            raise ValueError(f"Conversation {conversation_id} not found")

        position = len(row.messages)
        msg = MessageRow(
            conversation_id=conversation_id,
            role=role.value if isinstance(role, MessageRole) else str(role),
            content=content,
            image_url=image_url,
            position=position,
            created_at=datetime.utcnow(),
        )
        db.add(msg)

        if position == 0 and role == MessageRole.USER:
            row.title = content[:50] + ("..." if len(content) > 50 else "")
        row.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(msg)

        return ChatMessage(
            role=MessageRole(msg.role),
            content=msg.content,
            image_url=msg.image_url,
            timestamp=msg.created_at,
        )

    def get_messages_for_context(
        self,
        db: Session,
        conversation_id: str,
        max_messages: int = 10,
        user_id: Optional[str] = None,
    ) -> List[Dict]:
        row = self._get_row(db, conversation_id, user_id)
        if not row:
            return []
        recent = (row.messages or [])[-max_messages:]
        return [
            {
                "role": msg.role,
                "content": msg.content,
                "image_url": msg.image_url,
            }
            for msg in recent
        ]

    def list_conversations(
        self, db: Session, user_id: str, limit: int = 20
    ) -> List[Conversation]:
        stmt = (
            select(ConversationRow)
            .where(ConversationRow.user_id == user_id)
            .options(selectinload(ConversationRow.messages))
            .order_by(ConversationRow.updated_at.desc())
            .limit(limit)
        )
        rows = db.scalars(stmt).all()
        return [self._to_schema(r) for r in rows]

    def delete_conversation(
        self, db: Session, conversation_id: str, user_id: str
    ) -> bool:
        row = self._get_row(db, conversation_id, user_id, with_messages=False)
        if not row:
            return False
        db.execute(delete(MessageRow).where(MessageRow.conversation_id == conversation_id))
        db.delete(row)
        db.commit()
        return True

    def update_conversation_with_images(
        self,
        db: Session,
        conversation_id: str,
        image_urls: List[str],
        last_image_base64: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> None:
        row = self._get_row(db, conversation_id, user_id)
        if not row:
            return

        if last_image_base64:
            row.last_generated_image = last_image_base64

        if image_urls and row.messages:
            for msg in reversed(row.messages):
                if msg.role == MessageRole.ASSISTANT.value:
                    msg.image_url = "|||".join(image_urls)
                    print(
                        f"[ConversationService] Attached {len(image_urls)} images "
                        f"to assistant message"
                    )
                    break

        row.updated_at = datetime.utcnow()
        db.commit()
        print("[ConversationService] Saved conversation with images")

    def get_last_generated_image(
        self, db: Session, conversation_id: str, user_id: Optional[str] = None
    ) -> Optional[str]:
        row = self._get_row(db, conversation_id, user_id, with_messages=False)
        return row.last_generated_image if row else None

    def store_original_image(
        self,
        db: Session,
        conversation_id: str,
        image_base64: str,
        user_id: Optional[str] = None,
    ) -> None:
        row = self._get_row(db, conversation_id, user_id, with_messages=False)
        if row:
            row.original_image = image_base64
            row.updated_at = datetime.utcnow()
            db.commit()

    def get_original_image(
        self, db: Session, conversation_id: str, user_id: Optional[str] = None
    ) -> Optional[str]:
        row = self._get_row(db, conversation_id, user_id, with_messages=False)
        return row.original_image if row else None

    def store_mesh_reference(
        self,
        db: Session,
        conversation_id: str,
        mesh_id: str,
        user_id: Optional[str] = None,
    ) -> None:
        row = self._get_row(db, conversation_id, user_id, with_messages=False)
        if row:
            row.mesh_id = mesh_id
            row.updated_at = datetime.utcnow()
            db.commit()
            print(
                f"[ConversationService] Stored mesh {mesh_id} "
                f"for conversation {conversation_id}"
            )

    def get_mesh_id(
        self, db: Session, conversation_id: str, user_id: Optional[str] = None
    ) -> Optional[str]:
        row = self._get_row(db, conversation_id, user_id, with_messages=False)
        return row.mesh_id if row else None

    def has_mesh(
        self, db: Session, conversation_id: str, user_id: Optional[str] = None
    ) -> bool:
        return self.get_mesh_id(db, conversation_id, user_id) is not None


conversation_service = ConversationService()
