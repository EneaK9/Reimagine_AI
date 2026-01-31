"""
ReimagineAI - Pydantic Schemas for API
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


# ============ Enums ============

class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class DesignStyle(str, Enum):
    MODERN = "modern"
    MINIMALIST = "minimalist"
    INDUSTRIAL = "industrial"
    SCANDINAVIAN = "scandinavian"
    BOHEMIAN = "bohemian"
    TRADITIONAL = "traditional"
    CONTEMPORARY = "contemporary"
    RUSTIC = "rustic"
    FUTURISTIC = "futuristic"
    CLASSIC = "classic"


# ============ Chat Schemas ============

class ChatMessage(BaseModel):
    role: MessageRole
    content: str
    image_url: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    image_base64: Optional[str] = None  # Base64 encoded image
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "Make my living room more modern with plants",
                "conversation_id": "conv_123",
                "image_base64": None
            }
        }


class ChatResponse(BaseModel):
    conversation_id: str
    message: str
    generated_images: List[str] = []  # URLs to generated images
    furniture_suggestions: List[dict] = []
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ============ Image Generation Schemas ============

class ImageGenerationRequest(BaseModel):
    prompt: str
    style: Optional[DesignStyle] = DesignStyle.MODERN
    num_variations: int = Field(default=4, ge=1, le=4)
    reference_image_base64: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "prompt": "A cozy living room with warm lighting",
                "style": "modern",
                "num_variations": 4
            }
        }


class GeneratedImage(BaseModel):
    url: str
    prompt_used: str
    style: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ImageGenerationResponse(BaseModel):
    images: List[GeneratedImage]
    conversation_id: Optional[str] = None


# ============ Conversation Schemas ============

class Conversation(BaseModel):
    id: str
    title: str
    messages: List[ChatMessage] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    # For image editing context - stores images for follow-up edits
    original_image: Optional[str] = None  # Base64 of originally uploaded image
    last_generated_image: Optional[str] = None  # Base64 of last generated image for edits
    
    
class ConversationSummary(BaseModel):
    id: str
    title: str
    last_message: Optional[str] = None
    image_count: int = 0
    created_at: datetime
    updated_at: datetime


# ============ User Schemas ============

class UserBase(BaseModel):
    email: str
    username: str


class UserCreate(UserBase):
    password: str


class User(UserBase):
    id: str
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        from_attributes = True


# ============ Auth Schemas ============

class LoginRequest(BaseModel):
    email: str
    password: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com",
                "password": "password123"
            }
        }


class SignupRequest(BaseModel):
    username: str
    email: str
    password: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "username": "johndoe",
                "email": "john@example.com",
                "password": "password123"
            }
        }


class AuthResponse(BaseModel):
    id: str
    username: str
    email: str
    token: str
    created_at: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "user_abc123",
                "username": "johndoe",
                "email": "john@example.com",
                "token": "eyJhbGciOiJIUzI1NiIs...",
                "created_at": "2024-01-15T10:30:00"
            }
        }


# ============ Health Check ============

class HealthCheck(BaseModel):
    status: str = "healthy"
    version: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
