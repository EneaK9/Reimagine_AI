"""
ReimagineAI - Auth Router
Handles user authentication endpoints (login, signup, etc.)
"""
from fastapi import APIRouter, Depends, HTTPException, Header
from typing import Optional
from sqlalchemy.orm import Session

from ..models.schemas import (
    LoginRequest,
    SignupRequest,
    AuthResponse,
)
from ..services.user_service import user_service
from ..db.session import get_db
from ..deps import get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/signup", response_model=AuthResponse)
async def signup(request: SignupRequest, db: Session = Depends(get_db)):
    """Register a new user account."""
    try:
        user_data = user_service.signup(
            db,
            username=request.username,
            email=request.email,
            password=request.password,
        )
        return AuthResponse(**user_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")


@router.post("/login", response_model=AuthResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate user and return token."""
    try:
        user_data = user_service.login(
            db,
            email=request.email,
            password=request.password,
        )
        return AuthResponse(**user_data)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}")


@router.post("/logout")
async def logout(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """Logout user by invalidating their token."""
    if not authorization:
        raise HTTPException(status_code=401, detail="No authorization token provided")

    token = (
        authorization.replace("Bearer ", "", 1)
        if authorization.startswith("Bearer ")
        else authorization
    )
    user = user_service.verify_token(db, token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")

    user_service.logout(db, user["id"])
    return {"message": "Logged out successfully"}


@router.get("/me")
async def me(current_user: dict = Depends(get_current_user)):
    """Get current user info from token."""
    return current_user


@router.get("/verify")
async def verify_token(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """Verify if a token is valid."""
    if not authorization:
        return {"valid": False, "message": "No token provided"}

    token = (
        authorization.replace("Bearer ", "", 1)
        if authorization.startswith("Bearer ")
        else authorization
    )
    user = user_service.verify_token(db, token)
    return {"valid": user is not None, "user": user}
