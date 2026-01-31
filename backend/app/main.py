"""
ReimagineAI - Main FastAPI Application
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from datetime import datetime

from .config import get_settings
from .routers import chat, images, auth, rooms
from .models.schemas import HealthCheck

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan events.
    Startup and shutdown logic goes here.
    """
    # Startup
    print(f"[START] Starting {settings.app_name} v{settings.app_version}")
    print(f"[INFO] Debug mode: {settings.debug}")
    
    # Check OpenAI API key
    if not settings.openai_api_key:
        print("[WARNING] OpenAI API key not set! Set OPENAI_API_KEY in .env")
    else:
        print("[OK] OpenAI API key configured")
    
    yield
    
    # Shutdown
    print(f"[STOP] Shutting down {settings.app_name}")


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    description="""
    🏠 **ReimagineAI** - Transform your spaces with AI
    
    Upload photos of your rooms and get AI-powered redesign suggestions.
    
    ## Features
    - 💬 Chat with AI interior design assistant
    - 📸 Upload room photos for analysis
    - 🎨 Generate multiple design variations
    - 🛋️ Get furniture recommendations (coming soon)
    
    ## Getting Started
    1. Start a conversation at `/api/v1/chat/`
    2. Upload a room photo or describe what you want
    3. Receive 4 AI-generated design variations
    """,
    version=settings.app_version,
    lifespan=lifespan
)

# Configure CORS for mobile app
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "*",  # Allow all origins in development
        # In production, specify your app's domains:
        # "https://reimagineai.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(images.router, prefix="/api/v1")
app.include_router(rooms.router, prefix="/api/v1")


# ============ Root Endpoints ============

@app.get("/", tags=["Root"])
async def root():
    """
    Welcome endpoint with API information.
    """
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "description": "Transform your spaces with AI",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health", response_model=HealthCheck, tags=["Health"])
async def health_check():
    """
    Health check endpoint for monitoring.
    """
    return HealthCheck(
        status="healthy",
        version=settings.app_version,
        timestamp=datetime.utcnow()
    )


# ============ Error Handlers ============

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """
    Global exception handler for unhandled errors.
    """
    return {
        "error": True,
        "message": str(exc) if settings.debug else "An unexpected error occurred",
        "type": type(exc).__name__
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug
    )
