"""
ReimagineAI - Configuration Settings

API keys and secrets must come from environment variables or a local `.env`
file (see `.env.example`). Never hardcode real credentials in this module.
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App Settings
    app_name: str = "ReimagineAI"
    app_version: str = "0.1.0"
    debug: bool = True

    # API Keys — set OPENAI_API_KEY / GEMINI_API_KEY / FAL_API_KEY in the environment
    openai_api_key: str = ""

    # Database (local Homebrew / Docker Postgres)
    database_url: str = (
        "postgresql+psycopg://reimagine:reimagine@127.0.0.1:5432/reimagine_ai"
    )

    # JWT Settings — set SECRET_KEY in production
    secret_key: str = "your-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # File Storage
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    allowed_extensions: list = ["jpg", "jpeg", "png", "webp"]
    upload_dir: str = "uploads"

    # OpenAI Settings (for chat)
    gpt_model: str = "gpt-4-turbo-preview"

    # Google Gemini Settings (for room redesign - image editing)
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3-pro-image-preview"  # Supports image generation
    # Scene understanding layer: which vision provider reads the photo
    # ("openai" or "gemini"; the other is used as automatic fallback)
    scene_analysis_provider: str = "openai"
    openai_vision_model: str = "gpt-5-mini"
    # Gemini analysis model ("-latest" alias survives model retirements)
    gemini_analysis_model: str = "gemini-flash-latest"

    # Image-to-3D generation (per-object realistic meshes via fal.ai)
    # Set FAL_API_KEY in .env to enable the "Make realistic" feature.
    fal_api_key: str = ""
    # TRELLIS.2: much better geometry/texture than v1 for furniture
    image_to_3d_model: str = "fal-ai/trellis-2"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # Ignore extra fields in .env file


@lru_cache()
def get_settings() -> Settings:
    return Settings()
