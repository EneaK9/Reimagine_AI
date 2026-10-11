"""
ReimagineAI - Main FastAPI Application
"""
import asyncio
import os
import threading

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from datetime import datetime

from .config import get_settings
from .routers import chat, images, auth, rooms, depth, scenes
from .models.schemas import HealthCheck
from .db.session import check_database
from .services.depth_service import depth_service

settings = get_settings()

# Shared by CORSMiddleware and the 500 handler (which runs outside it)
CORS_ALLOW_ORIGINS = [
    "*",  # Allow all origins in development
    # In production, specify your app's domains:
    # "https://reimagineai.app",
]

HEALTH_DB_TIMEOUT_S = 3.0


def _preload_depth_model_enabled() -> bool:
    """PRELOAD_DEPTH_MODEL=0/false disables the startup warm-up (default: on)."""
    value = os.environ.get("PRELOAD_DEPTH_MODEL", "1").strip().lower()
    return value not in ("0", "false", "no", "off")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan events.
    Startup and shutdown logic goes here.
    """
    # Startup
    print(f"[START] Starting {settings.app_name} v{settings.app_version}")
    print(f"[INFO] Debug mode: {settings.debug}")

    try:
        from .db.session import init_db

        init_db()
        print("[OK] PostgreSQL ready")
    except Exception as e:
        print(f"[ERROR] Database init failed: {e}")
        raise
    
    # Check OpenAI API key
    if not settings.openai_api_key:
        print("[WARNING] OpenAI API key not set! Set OPENAI_API_KEY in .env")
    else:
        print("[OK] OpenAI API key configured")
    print(f"[INFO] OpenAI model: {settings.gpt_model}")

    # Load the scene depth model in the background so the first scene
    # request doesn't pay for it. Never blocks startup.
    if _preload_depth_model_enabled():
        threading.Thread(
            target=depth_service.warm_up, name="depth-warm-up", daemon=True
        ).start()
        print("[INFO] Warming up depth model in the background")
    else:
        print("[INFO] Depth model preload disabled (PRELOAD_DEPTH_MODEL)")

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
    allow_origins=CORS_ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(images.router, prefix="/api/v1")
app.include_router(rooms.router, prefix="/api/v1")
app.include_router(depth.router, prefix="/api/v1")
app.include_router(scenes.router, prefix="/api/v1")


# ============ 3D Editor (static) ============

@app.get("/editor", tags=["3D Scenes"])
async def editor_page():
    """
    Interactive 3D room editor (three.js).
    - Mobile app embeds it in a WebView (JS-bridge mode).
    - Flutter web opens it in a new tab as /editor?scene_id=...&token=...
      (standalone mode: the page talks to the API directly).
    """
    import os
    from fastapi.responses import FileResponse

    path = os.path.join(os.path.dirname(__file__), "static", "editor.html")
    return FileResponse(path, media_type="text/html")


@app.get("/privacy", tags=["Legal"])
async def privacy_policy_page():
    """Public Privacy Policy page (required for Google Play / store listings)."""
    import os
    from fastapi.responses import HTMLResponse

    path = os.path.join(os.path.dirname(__file__), "static", "privacy.html")
    with open(path, encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.get("/delete-account", tags=["Legal"])
async def delete_account_page():
    """Public account-deletion request page (required for Google Play Data safety)."""
    import os
    from fastapi.responses import HTMLResponse

    path = os.path.join(os.path.dirname(__file__), "static", "delete-account.html")
    with open(path, encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


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


class HealthStatus(HealthCheck):
    """HealthCheck plus the database probe result: "ok" or "error"."""
    database: str = "unknown"


@app.get("/health", response_model=HealthStatus, tags=["Health"])
async def health_check():
    """
    Health check endpoint for monitoring.
    Always 200 while the process is up (the Docker healthcheck relies on it);
    "database" reports a quick SELECT 1 probe run off the event loop.
    """
    try:
        db_ok = await asyncio.wait_for(
            asyncio.to_thread(check_database), timeout=HEALTH_DB_TIMEOUT_S
        )
    except Exception:  # includes the timeout
        db_ok = False
    return HealthStatus(
        status="healthy",
        version=settings.app_version,
        timestamp=datetime.utcnow(),
        database="ok" if db_ok else "error",
    )


# ============ Error Handlers ============

def _cors_error_headers(request: Request) -> dict:
    """
    CORS headers for the 500 handler. Starlette runs the Exception handler in
    its outermost ServerErrorMiddleware, outside CORSMiddleware, so without
    these browsers (Flutter web) hide the error response from the app.
    """
    origin = request.headers.get("origin")
    if not origin:
        return {}
    if "*" not in CORS_ALLOW_ORIGINS and origin not in CORS_ALLOW_ORIGINS:
        return {}
    return {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Credentials": "true",
        "Vary": "Origin",
    }


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Global exception handler for unhandled errors.
    HTTPException and request validation errors keep FastAPI's default
    handlers. Exception details are only returned in debug mode; Starlette
    re-raises afterwards, so the server still logs the full traceback.
    """
    print(f"[ERROR] Unhandled {type(exc).__name__} on {request.method} {request.url.path}: {exc}")
    content = {
        "error": True,
        "message": "An unexpected error occurred",
    }
    if settings.debug:
        content["detail"] = str(exc)
        content["type"] = type(exc).__name__
    return JSONResponse(status_code=500, content=content, headers=_cors_error_headers(request))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug
    )
