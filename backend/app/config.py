"""
ReimagineAI - Configuration Settings

API keys and secrets must come from environment variables or a local `.env`
file (see `.env.example`). Never hardcode real credentials in this module.
"""
from pydantic import model_validator
from pydantic_settings import BaseSettings
from functools import lru_cache

# Pin chat and vision to one dated snapshot so the ID cannot silently retarget.
# Also remap retired preview names (shut down 2026-03-26) and the previous
# gpt-4.1 / gpt-5-mini defaults so a stale production .env still works.
_DEFAULT_GPT_MODEL = "gpt-4.1-2025-04-14"
_RETIRED_GPT_MODELS = {
    "gpt-4-turbo-preview": _DEFAULT_GPT_MODEL,
    "gpt-4-0125-preview": _DEFAULT_GPT_MODEL,
    "gpt-4-1106-preview": _DEFAULT_GPT_MODEL,
    "gpt-4.1": _DEFAULT_GPT_MODEL,
    "gpt-5-mini": _DEFAULT_GPT_MODEL,
}


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

    # OpenAI Settings (chat + vision). One dated snapshot for both.
    gpt_model: str = _DEFAULT_GPT_MODEL

    # Google Gemini Settings (for room redesign - image editing)
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3-pro-image-preview"  # Supports image generation
    # Scene understanding layer: which vision provider reads the photo
    # ("openai" or "gemini"; the other is used as automatic fallback)
    scene_analysis_provider: str = "openai"
    openai_vision_model: str = _DEFAULT_GPT_MODEL
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

    @model_validator(mode="after")
    def remap_retired_openai_models(self):
        for field in ("gpt_model", "openai_vision_model"):
            current = getattr(self, field).strip()
            replacement = _RETIRED_GPT_MODELS.get(current)
            if replacement and replacement != current:
                print(
                    f"[WARNING] {field} '{current}' is not the pinned model; "
                    f"using '{replacement}' instead"
                )
                setattr(self, field, replacement)
        return self


@lru_cache()
def get_settings() -> Settings:
    return Settings()
