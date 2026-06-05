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


class UnitSystem(str, Enum):
    METRIC = "metric"
    IMPERIAL = "imperial"


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
    prompt: str = ""
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
    unit_system: Optional[UnitSystem] = None
    yard_length: Optional[float] = Field(default=None, ge=0, description="Yard length in chosen unit_system (m or ft)")
    yard_width: Optional[float] = Field(default=None, ge=0, description="Yard width in chosen unit_system (m or ft)")
    plant_spec: Optional[str] = Field(default=None, description="Plant specification text for including recommended plants in image generation")


class RoomUpgradeGenerateResponse(BaseModel):
    after_image_url: Optional[str] = None
    generated_images: List[str] = Field(default_factory=list)
    prompt_used: str


# ============ Yard Designer Schemas ============

class CityContext(str, Enum):
    COASTAL = "coastal"
    INLAND = "inland"
    UNKNOWN = "unknown"


class LocationProfile(BaseModel):
    """
    Structured climate profile derived dynamically from city/location.
    Intended to be produced by a location intelligence LLM call and validated here.
    """
    city: str
    country_or_region: Optional[str] = None
    city_context: Optional[CityContext] = None

    usda_hardiness_zone: Optional[str] = None
    annual_rainfall_mm: Optional[float] = Field(default=None, ge=0)
    monthly_rainfall_mm: Optional[List[float]] = None  # Jan–Dec
    summer_dry_months: Optional[List[str]] = None
    irrigation_required: Optional[Literal["mandatory", "recommended", "not_needed"]] = None

    july_avg_high_c: Optional[float] = None
    july_avg_high_f: Optional[float] = None
    shade_structure_priority: Optional[Literal["mandatory", "recommended", "optional"]] = None

    last_spring_frost_date: Optional[str] = None
    first_autumn_frost_date: Optional[str] = None
    first_frost_month: Optional[int] = Field(default=None, ge=1, le=12)
    growing_season_days: Optional[int] = Field(default=None, ge=0)

    annual_sunshine_hours: Optional[int] = Field(default=None, ge=0)
    solar_lighting_viability: Optional[Literal["year_round", "summer_only", "not_recommended"]] = None

    uv_index_summer: Optional[int] = Field(default=None, ge=0)
    uv_rated_materials_required: Optional[Literal["mandatory", "recommended", "standard"]] = None

    summer_humidity_pct: Optional[float] = Field(default=None, ge=0, le=100)
    humidity_risk_level: Optional[Literal["low", "moderate", "high", "tropical"]] = None

    avg_wind_kmh: Optional[float] = Field(default=None, ge=0)
    prevailing_wind_direction: Optional[str] = None
    wind_risk_level: Optional[Literal["low", "moderate", "high"]] = None

    elevation_m: Optional[float] = Field(default=None, ge=0)
    uv_altitude_adjustment_needed: Optional[Literal["yes", "no"]] = None
    uv_altitude_uplift_pct: Optional[float] = Field(default=None, ge=0)

    special_flags: List[str] = Field(default_factory=list)
    plant_hardiness_summary: Optional[str] = None
    material_durability_summary: Optional[str] = None

    data_quality: Optional[Literal["high", "medium", "low"]] = None
    assumptions: List[str] = Field(default_factory=list)


class YardDesignInputs(BaseModel):
    """
    Optional inputs for yard design advisor.
    All fields are optional - the system works without them,
    but each input improves the advice quality.
    """
    unit_system: Optional[UnitSystem] = Field(default=None, description="Preferred measurement system for yard + product dimensions")
    yard_length: Optional[float] = Field(default=None, ge=0, description="Yard length in chosen unit_system (m or ft)")
    yard_width: Optional[float] = Field(default=None, ge=0, description="Yard width in chosen unit_system (m or ft)")
    dimensions_sqm: Optional[float] = Field(default=None, ge=0, description="Approximate space size in square meters (computed internally from yard_length×yard_width when provided)")
    orientation: Optional[Literal["north", "south", "east", "west"]] = Field(default=None, description="Compass direction the space faces")
    surface_type: Optional[Literal["grass", "concrete", "gravel", "decking", "bare_soil", "mixed"]] = Field(default=None, description="Primary ground surface")
    slope: Optional[Literal["flat", "gentle", "significant"]] = Field(default=None, description="Ground slope level")
    city_or_region: Optional[str] = Field(default=None, description="City or region for climate determination")
    city_context: Optional[CityContext] = Field(default=None, description="City context: coastal vs inland vs unknown")
    environment_type: Optional[Literal["coastal", "suburban", "urban", "rural", "mountain"]] = Field(default=None, description="Type of environment")
    primary_purpose: Optional[Literal["dining", "relaxing", "children_play", "food_growing", "aesthetic"]] = Field(default=None, description="Main intended use")
    who_uses: Optional[List[str]] = Field(default=None, description="Who uses the space: adults, children, dogs, cats, elderly, etc.")
    maintenance: Optional[Literal["low", "medium", "high"]] = Field(default=None, description="Maintenance time tolerance")
    style_preference: Optional[str] = Field(default=None, description="Design style: modern, rustic, coastal, etc.")
    ownership: Optional[Literal["owner", "renter"]] = Field(default=None, description="Ownership status affects what can be installed")


class DesignConstraint(BaseModel):
    """A design constraint that applies to the user's situation."""
    title: str = Field(description="Short constraint name, e.g. 'Coastal Environment'")
    explanation: str = Field(description="Why this matters, written naturally")
    impact: str = Field(description="What this means for the design")
    user_action: str = Field(description="What the user should do or be aware of")


class ActionStep(BaseModel):
    """A step in the action plan for the user."""
    step: int = Field(description="Step number")
    action: str = Field(description="Brief action title")
    detail: str = Field(description="Specific instructions")
    reasoning: str = Field(description="Why this step matters")


class ProductRequirement(BaseModel):
    """Requirements for a product category based on constraints."""
    category: str = Field(description="Product category, e.g. seating, planters, lighting")
    requirements: str = Field(description="Specific requirements based on constraints")
    search_terms: List[str] = Field(default_factory=list, description="Suggested search keywords")
    budget_allocation: float = Field(default=0, ge=0, description="Suggested budget for this category")
    placement: str = Field(default="", description="Where in the space")


class DesignWarning(BaseModel):
    """A warning about the design or constraints."""
    severity: Literal["critical", "important", "info"] = Field(description="Warning severity level")
    title: str = Field(description="Short warning title")
    message: str = Field(description="Detailed explanation")


class SeasonalNotes(BaseModel):
    """Seasonal care and expectations."""
    spring: Optional[str] = None
    summer: Optional[str] = None
    autumn: Optional[str] = None
    winter: Optional[str] = None


class SpaceAssessment(BaseModel):
    """Assessment of the user's space."""
    summary: str = Field(description="Brief description of the space and situation")
    size_category: Optional[str] = Field(default=None, description="micro/small/medium/large")
    key_characteristics: List[str] = Field(default_factory=list, description="Notable features")


class DesignApproach(BaseModel):
    """The overall design approach."""
    strategy: str = Field(description="Overall approach in one sentence")
    reasoning: str = Field(description="Why this approach works")
    focal_point: Optional[str] = Field(default=None, description="Main visual anchor")
    zones: List[str] = Field(default_factory=list, description="Defined areas in the design")


class YardDesignAdvice(BaseModel):
    """
    Comprehensive design advice generated by the yard advisor.
    Contains reasoning, constraints, action plan, and product requirements.
    """
    space_assessment: Optional[SpaceAssessment] = None
    key_constraints: List[DesignConstraint] = Field(default_factory=list)
    design_approach: Optional[DesignApproach] = None
    action_plan: List[ActionStep] = Field(default_factory=list)
    product_requirements: List[ProductRequirement] = Field(default_factory=list)
    warnings: List[DesignWarning] = Field(default_factory=list)
    seasonal_notes: Optional[SeasonalNotes] = None


class YardUpgradeAnalyzeResponse(BaseModel):
    """
    Extended response that includes design advice alongside products.
    Backward compatible with RoomUpgradeAnalyzeResponse.
    """
    # Design advice (only present if yard inputs were provided)
    design_advice: Optional[YardDesignAdvice] = None
    # Optional derived location profile and plant specification
    location_profile: Optional[LocationProfile] = None
    plant_spec: Optional[str] = None
    # Standard room upgrade fields
    scene_analysis: SceneAnalysis
    search_results: List[ProductSearchResult] = Field(default_factory=list)
    selected_products: List[SelectedProduct] = Field(default_factory=list)
    total_estimated: float = 0
    within_budget: bool = True
    budget: float
    currency: str = "USD"


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
