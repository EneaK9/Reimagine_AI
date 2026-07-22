"""
FastAPI dependencies — DB session + authenticated user.
"""
from typing import Dict, Optional

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from .db.session import get_db
from .services.user_service import user_service


def get_optional_user(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> Optional[Dict]:
    if not authorization:
        return None
    token = (
        authorization.replace("Bearer ", "", 1)
        if authorization.startswith("Bearer ")
        else authorization
    )
    return user_service.verify_token(db, token)


def get_current_user(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> Dict:
    if not authorization:
        raise HTTPException(status_code=401, detail="Authentication required")
    token = (
        authorization.replace("Bearer ", "", 1)
        if authorization.startswith("Bearer ")
        else authorization
    )
    user = user_service.verify_token(db, token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user
