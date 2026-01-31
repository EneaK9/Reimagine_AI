"""
ReimagineAI - Auth Router
Handles user authentication endpoints (login, signup, etc.)
"""
from fastapi import APIRouter, HTTPException, Header
from typing import Optional

from ..models.schemas import (
    LoginRequest,
    SignupRequest,
    AuthResponse
)
from ..services.user_service import user_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/signup", response_model=AuthResponse)
async def signup(request: SignupRequest):
    """
    Register a new user account.
    
    Returns user data with authentication token on success.
    """
    try:
        user_data = user_service.signup(
            username=request.username,
            email=request.email,
            password=request.password
        )
        return AuthResponse(**user_data)
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")


@router.post("/login", response_model=AuthResponse)
async def login(request: LoginRequest):
    """
    Authenticate user and return token.
    
    Returns user data with authentication token on success.
    """
    try:
        user_data = user_service.login(
            email=request.email,
            password=request.password
        )
        return AuthResponse(**user_data)
    
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}")


@router.post("/logout")
async def logout(authorization: Optional[str] = Header(None)):
    """
    Logout user by invalidating their token.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="No authorization token provided")
    
    # Extract token from "Bearer <token>" format
    token = authorization.replace("Bearer ", "") if authorization.startswith("Bearer ") else authorization
    
    user = user_service.verify_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user_service.logout(user['id'])
    
    return {"message": "Logged out successfully"}


@router.get("/me")
async def get_current_user(authorization: Optional[str] = Header(None)):
    """
    Get current user info from token.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="No authorization token provided")
    
    token = authorization.replace("Bearer ", "") if authorization.startswith("Bearer ") else authorization
    
    user = user_service.verify_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    return user


@router.get("/verify")
async def verify_token(authorization: Optional[str] = Header(None)):
    """
    Verify if a token is valid.
    """
    if not authorization:
        return {"valid": False, "message": "No token provided"}
    
    token = authorization.replace("Bearer ", "") if authorization.startswith("Bearer ") else authorization
    
    user = user_service.verify_token(token)
    
    return {
        "valid": user is not None,
        "user": user
    }
