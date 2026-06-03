"""
ReimagineAI - Pydantic Schemas for API
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Literal
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
    mesh_id: Optional[str] = None  # ID of 3D mesh to edit
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "Make my living room more modern with plants",
                "conversation_id": "conv_123",
                "image_base64": None,
                "mesh_id": None
            }
        }


class ChatResponse(BaseModel):
    conversation_id: str
    message: str
    generated_images: List[str] = []  # URLs to generated images
    furniture_suggestions: List[dict] = []
    mesh_url: Optional[str] = None  # URL to updated 3D mesh (if conversation has mesh)
    mesh_id: Optional[str] = None  # ID of mesh for future edits
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


# ============ Room Upgrade Schemas ============

class ShoppingListItem(BaseModel):
    item_name: str
    search_description: str
    budget_allocation: float = Field(ge=0)
    placement: str
    priority: Literal["must-have", "nice-to-have"] = "must-have"


class Product(BaseModel):
    title: str
    price: float = Field(ge=0)
    currency: str = "USD"
    image_url: str
    buy_link: str
    store: str
    rating: Optional[float] = None
    review_count: Optional[int] = None
    description: Optional[str] = None
    # Enhanced fields for better Gemini prompts
    detailed_description: Optional[str] = None
    dimensions: Optional[str] = None
    material: Optional[str] = None
    color: Optional[str] = None
    brand: Optional[str] = None
    # High-res image for Gemini multi-image fusion
    high_res_image_url: Optional[str] = None
    # SerpAPI detail endpoint used only after final selection to resolve direct merchant links
    serpapi_immersive_product_api: Optional[str] = None


class ProductSearchResult(BaseModel):
    shopping_list_item: ShoppingListItem
    all_candidates: List[Product] = Field(default_factory=list)


class SelectedProduct(BaseModel):
    shopping_list_item: ShoppingListItem
    chosen_product: Product
    all_candidates: List[Product] = Field(default_factory=list)
    reasoning: Optional[str] = None


class SceneAnalysis(BaseModel):
    space_type: str
    existing_items: List[str] = Field(default_factory=list)
    style_observation: str
    shopping_list: List[ShoppingListItem] = Field(default_factory=list)


class RoomUpgradeAnalyzeRequest(BaseModel):
    image_base64: str
    prompt: str
    budget: Optional[float] = Field(default=None, ge=0)
    currency: str = "USD"


class RoomUpgradeAnalyzeResponse(BaseModel):
    scene_analysis: SceneAnalysis
    search_results: List[ProductSearchResult] = Field(default_factory=list)
    selected_products: List[SelectedProduct] = Field(default_factory=list)
    total_estimated: float = 0
    within_budget: bool = True
    budget: float
    currency: str = "USD"


class RoomUpgradeSearchRequest(BaseModel):
    shopping_list: List[ShoppingListItem]
    budget: float = Field(ge=0)
    currency: str = "USD"


class RoomUpgradeGenerateRequest(BaseModel):
    image_base64: str
    prompt: str = ""
    scene_analysis: SceneAnalysis
    selected_products: List[SelectedProduct]


class RoomUpgradeGenerateResponse(BaseModel):
    after_image_url: Optional[str] = None
    generated_images: List[str] = Field(default_factory=list)
    prompt_used: str


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
    # For 3D mesh generation
    mesh_id: Optional[str] = None  # ID of associated 3D mesh
    
    
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


# ============ Depth/Mesh Schemas ============

class MeshGenerationRequest(BaseModel):
    image_base64: str
    conversation_id: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "image_base64": "<base64 encoded image>",
                "conversation_id": "conv_123"
            }
        }


class MeshGenerationResponse(BaseModel):
    mesh_id: str
    mesh_url: str
    depth_map_url: str
    conversation_id: Optional[str] = None
    original_size: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class MeshInfo(BaseModel):
    mesh_id: str
    mesh_url: str
    size_bytes: int
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ============ Health Check ============

class HealthCheck(BaseModel):
    status: str = "healthy"
    version: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
