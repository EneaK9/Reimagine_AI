"""
ReimagineAI - Configuration Settings
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App Settings
    app_name: str = "ReimagineAI"
    app_version: str = "0.1.0"
    debug: bool = True
    
    # API Keys
    openai_api_key: str = ""
    
    # Database
    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/reimagine_ai"
    
    # JWT Settings
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
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # Ignore extra fields in .env file


@lru_cache()
def get_settings() -> Settings:
    return Settings()
