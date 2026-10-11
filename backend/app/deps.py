"""
ReimagineAI - FastAPI dependencies and request helpers
DB session + authenticated user, plus upload size limits shared by routers.
"""
from typing import Dict, Optional

from fastapi import Depends, Header, HTTPException, UploadFile
from sqlalchemy.orm import Session

from .config import get_settings
from .db.session import get_db
from .services.user_service import user_service

settings = get_settings()

_READ_CHUNK_BYTES = 1024 * 1024
# Slack for a "data:image/...;base64," prefix, padding and line breaks
_BASE64_OVERHEAD_CHARS = 1024


def _lookup_token_user(db: Session, token: str) -> Optional[Dict]:
    user = user_service.verify_token(db, token)
    # End the lookup's read transaction so long-running endpoints (AI calls,
    # mesh builds) don't hold a pooled connection "idle in transaction".
    # The session stays usable; its next query starts a new transaction.
    db.rollback()
    return user


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
    return _lookup_token_user(db, token)


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
    user = _lookup_token_user(db, token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user


# ============ Upload size limits ============

def _too_large(limit: int) -> HTTPException:
    return HTTPException(
        status_code=413,
        detail=f"File too large. Maximum size is {limit / (1024 * 1024):g} MB",
    )


async def read_upload_limited(upload: UploadFile, max_bytes: Optional[int] = None) -> bytes:
    """
    Read a multipart upload, enforcing a size limit.

    Usage: `data = await read_upload_limited(image)` (it is async).
    Reads at most max_bytes + 1 bytes from the current position, so an
    oversized file is never fully buffered in memory.

    Args:
        upload: The UploadFile from a File(...) parameter.
        max_bytes: Limit in bytes (default: settings.max_file_size, 10 MB).

    Raises:
        HTTPException 413 if the file is larger than the limit,
        HTTPException 400 if it is empty.
    """
    limit = settings.max_file_size if max_bytes is None else max_bytes
    # Starlette records the spooled size; reject early without reading
    if upload.size is not None and upload.size > limit:
        raise _too_large(limit)

    chunks = []
    remaining = limit + 1
    while remaining > 0:
        chunk = await upload.read(min(remaining, _READ_CHUNK_BYTES))
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    data = b"".join(chunks)

    if len(data) > limit:
        raise _too_large(limit)
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    return data


def max_base64_length(max_bytes: Optional[int] = None) -> int:
    """Longest accepted base64 string for a payload of max_bytes (default settings.max_file_size)."""
    limit = settings.max_file_size if max_bytes is None else max_bytes
    return limit * 4 // 3 + _BASE64_OVERHEAD_CHARS


def check_base64_size(b64: Optional[str], max_bytes: Optional[int] = None) -> None:
    """
    Reject an oversized base64 image string (plain or data URL) from a JSON body.

    Call it before decoding. None or "" passes (callers decide whether the
    field is required). The limit is the decoded size (default
    settings.max_file_size); the string may be about 4/3 of that.

    Raises:
        HTTPException 413 if the string is longer than max_base64_length().
    """
    if b64 and len(b64) > max_base64_length(max_bytes):
        raise _too_large(settings.max_file_size if max_bytes is None else max_bytes)
