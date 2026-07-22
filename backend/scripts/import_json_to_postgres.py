#!/usr/bin/env python3
"""
One-time import of legacy JSON storage into PostgreSQL.

Usage (from backend/):
  source venv/bin/activate
  python scripts/import_json_to_postgres.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db.session import SessionLocal, init_db
from app.db.models import User, Conversation, Message


def _parse_dt(value) -> datetime:
    if not value:
        return datetime.utcnow()
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(
            tzinfo=None
        )
    except Exception:
        return datetime.utcnow()


def main() -> None:
    data_dir = ROOT / "data"
    users_file = data_dir / "users.json"
    convs_file = data_dir / "conversations.json"

    init_db()
    db = SessionLocal()

    imported_users = 0
    imported_convs = 0
    imported_msgs = 0

    # Users
    if users_file.exists():
        users = json.loads(users_file.read_text(encoding="utf-8"))
        for user_id, u in users.items():
            if db.get(User, user_id):
                continue
            db.add(
                User(
                    id=user_id,
                    username=u["username"],
                    email=u["email"].lower(),
                    password_hash=u["password_hash"],
                    salt=u["salt"],
                    token=u.get("token"),
                    created_at=_parse_dt(u.get("created_at")),
                    updated_at=_parse_dt(u.get("updated_at")),
                )
            )
            imported_users += 1
        db.commit()

    # Pick a fallback owner for orphan conversations
    fallback_user = db.query(User).order_by(User.created_at.asc()).first()

    if convs_file.exists():
        convs = json.loads(convs_file.read_text(encoding="utf-8"))
        for conv_id, c in convs.items():
            if db.get(Conversation, conv_id):
                continue
            owner_id = c.get("user_id")
            if not owner_id or not db.get(User, owner_id):
                if not fallback_user:
                    print(
                        f"Skip conversation {conv_id}: no users in DB to assign ownership"
                    )
                    continue
                owner_id = fallback_user.id

            row = Conversation(
                id=conv_id,
                user_id=owner_id,
                title=c.get("title") or "Imported chat",
                original_image=c.get("original_image"),
                last_generated_image=c.get("last_generated_image"),
                mesh_id=c.get("mesh_id"),
                created_at=_parse_dt(c.get("created_at")),
                updated_at=_parse_dt(c.get("updated_at")),
            )
            db.add(row)
            db.flush()
            imported_convs += 1

            for i, m in enumerate(c.get("messages") or []):
                db.add(
                    Message(
                        conversation_id=conv_id,
                        role=m.get("role") or "user",
                        content=m.get("content") or "",
                        image_url=m.get("image_url"),
                        position=i,
                        created_at=_parse_dt(m.get("timestamp")),
                    )
                )
                imported_msgs += 1
        db.commit()

    db.close()
    print(
        f"Import complete — users={imported_users}, "
        f"conversations={imported_convs}, messages={imported_msgs}"
    )


if __name__ == "__main__":
    main()
