"""
ReimagineAI - App-level tests: 500 handler, /health, auth coverage, router fixes

The full app is imported, but its lifespan (PostgreSQL init, model warm-up)
never runs because TestClient is used without a `with` block. External AI
calls and the depth pipeline are monkeypatched; no network or database needed.
"""
import asyncio
import importlib
import inspect
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from starlette.exceptions import HTTPException as StarletteHTTPException

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import deps, main  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.deps import get_current_user  # noqa: E402
from app.routers import depth as depth_router  # noqa: E402
from app.routers import images as images_router  # noqa: E402
from app.routers import rooms as rooms_router  # noqa: E402
from app.services.gemini_service import gemini_service  # noqa: E402
from app.services.openai_service import openai_service  # noqa: E402

# app.services re-exports the singleton under the module's name
gemini_module = importlib.import_module("app.services.gemini_service")

ORIGIN = "https://app.example"
TEST_USER = {"id": "user_test123456", "username": "tester", "email": "tester@example.com"}


# ============ Global exception handler ============

def _error_app() -> FastAPI:
    """Minimal app wired like app.main: same CORS config and the same 500 handler."""
    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=main.CORS_ALLOW_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_exception_handler(Exception, main.global_exception_handler)

    @app.get("/boom")
    async def boom():
        raise RuntimeError("secret internals")

    @app.get("/missing")
    async def missing():
        raise HTTPException(status_code=404, detail="Nope")

    @app.get("/items/{item_id}")
    async def item(item_id: int):
        return {"item_id": item_id}

    return app


def test_unhandled_error_returns_json_500_with_cors(monkeypatch):
    monkeypatch.setattr(main.settings, "debug", False)
    client = TestClient(_error_app(), raise_server_exceptions=False)

    resp = client.get("/boom", headers={"Origin": ORIGIN})

    assert resp.status_code == 500
    assert resp.headers["content-type"].startswith("application/json")
    assert resp.json() == {"error": True, "message": "An unexpected error occurred"}
    assert "secret internals" not in resp.text
    assert resp.headers["access-control-allow-origin"] == ORIGIN


def test_unhandled_error_includes_detail_only_in_debug(monkeypatch):
    monkeypatch.setattr(main.settings, "debug", True)
    client = TestClient(_error_app(), raise_server_exceptions=False)

    body = client.get("/boom").json()

    assert body["message"] == "An unexpected error occurred"
    assert body["detail"] == "secret internals"
    assert body["type"] == "RuntimeError"


def test_http_and_validation_errors_keep_default_handlers():
    client = TestClient(_error_app(), raise_server_exceptions=False)

    missing = client.get("/missing", headers={"Origin": ORIGIN})
    assert missing.status_code == 404 and missing.json() == {"detail": "Nope"}
    assert "access-control-allow-origin" in missing.headers

    invalid = client.get("/items/not-a-number")
    assert invalid.status_code == 422
    assert isinstance(invalid.json()["detail"], list)


def test_real_app_registers_handlers():
    handlers = main.app.exception_handlers
    assert handlers[Exception] is main.global_exception_handler
    assert handlers[StarletteHTTPException] is http_exception_handler
    assert handlers[RequestValidationError] is request_validation_exception_handler


# ============ /health ============

def test_health_reports_database_ok(monkeypatch):
    monkeypatch.setattr(main, "check_database", lambda: True)
    resp = TestClient(main.app).get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "healthy" and body["database"] == "ok"
    assert body["version"] == main.settings.app_version


def test_health_reports_database_error_and_times_out(monkeypatch):
    monkeypatch.setattr(main, "check_database", lambda: False)
    resp = TestClient(main.app).get("/health")
    assert resp.status_code == 200 and resp.json()["database"] == "error"

    def slow_ok():
        time.sleep(0.5)
        return True

    # A probe slower than the timeout is reported as an error, not awaited
    monkeypatch.setattr(main, "check_database", slow_ok)
    monkeypatch.setattr(main, "HEALTH_DB_TIMEOUT_S", 0.05)
    resp = TestClient(main.app).get("/health")
    assert resp.status_code == 200 and resp.json()["database"] == "error"


# ============ Auth coverage ============

PUBLIC_ROUTES = {("GET", "/depth/mesh/{mesh_id}")}


def _dependency_calls(dependant):
    for dep in dependant.dependencies:
        yield dep.call
        yield from _dependency_calls(dep)


def test_images_depth_rooms_routes_require_auth():
    checked = 0
    routes = images_router.router.routes + depth_router.router.routes + rooms_router.router.routes
    for route in routes:
        assert isinstance(route, APIRoute)
        requires_auth = get_current_user in set(_dependency_calls(route.dependant))
        for method in route.methods:
            expected = (method, route.path) not in PUBLIC_ROUTES
            assert requires_auth == expected, (method, route.path)
            checked += 1
    assert checked >= 19


def test_requests_without_token_are_rejected_but_glb_stays_public():
    client = TestClient(main.app)
    assert client.get("/api/v1/depth/meshes").status_code == 401
    assert client.delete("/api/v1/depth/mesh/mesh_000000000000").status_code == 401
    assert client.get("/api/v1/images/styles").status_code == 401
    assert client.post("/api/v1/images/generate", json={"prompt": "x"}).status_code == 401
    assert client.get("/api/v1/rooms").status_code == 401
    # model-viewer fetches the GLB without an Authorization header
    assert client.get("/api/v1/depth/mesh/mesh_doesnotexist").status_code == 404


# ============ Router fixes (authenticated) ============

class FakeDB:
    def __init__(self):
        self.rolled_back = False

    def rollback(self):
        self.rolled_back = True


@pytest.fixture
def authed():
    fake_db = FakeDB()
    main.app.dependency_overrides[get_current_user] = lambda: TEST_USER
    main.app.dependency_overrides[get_db] = lambda: fake_db
    yield TestClient(main.app, raise_server_exceptions=False), fake_db
    main.app.dependency_overrides.clear()


FAKE_MESH = {
    "mesh_id": "mesh_abc123def456",
    "mesh_path": "/tmp/mesh_abc123def456.glb",
    "depth_map_url": "data:image/png;base64,AAAA",
    "original_size": {"width": 4, "height": 3},
}


def test_real_app_unhandled_router_error_is_json_with_cors(monkeypatch, authed):
    client, _ = authed
    monkeypatch.setattr(main.settings, "debug", False)

    async def broken_get_room(room_id):
        raise KeyError("rooms.json corrupted")

    monkeypatch.setattr(rooms_router.room_service, "get_room", broken_get_room)
    resp = client.get("/api/v1/rooms/room_abc", headers={"Origin": ORIGIN})

    assert resp.status_code == 500
    assert resp.json() == {"error": True, "message": "An unexpected error occurred"}
    assert resp.headers["access-control-allow-origin"] == ORIGIN


def test_generate_mesh_links_conversation_with_db_and_user(monkeypatch, authed):
    client, fake_db = authed
    calls = []
    monkeypatch.setattr(depth_router, "_build_mesh_sync", lambda image_base64: dict(FAKE_MESH))
    monkeypatch.setattr(
        depth_router.conversation_service,
        "store_mesh_reference",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    resp = client.post(
        "/api/v1/depth/generate-mesh",
        json={"image_base64": "aGVsbG8=", "conversation_id": "conv_1"},
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["mesh_url"] == "/api/v1/depth/mesh/mesh_abc123def456"
    assert calls == [((fake_db, "conv_1", "mesh_abc123def456"), {"user_id": TEST_USER["id"]})]


def test_mesh_build_runs_off_the_event_loop(monkeypatch, authed):
    def slow_build(image_base64):
        time.sleep(1.0)  # blocking, like the real CPU-bound pipeline
        return dict(FAKE_MESH)

    monkeypatch.setattr(depth_router, "_build_mesh_sync", slow_build)
    monkeypatch.setattr(main, "check_database", lambda: True)

    async def scenario():
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            t0 = time.monotonic()
            mesh_task = asyncio.create_task(
                client.post("/api/v1/depth/generate-mesh", json={"image_base64": "aGVsbG8="})
            )
            await asyncio.sleep(0.2)  # the mesh build is now running
            health = await client.get("/health")
            health_done = time.monotonic() - t0
            mesh = await mesh_task
            mesh_done = time.monotonic() - t0
        return health, health_done, mesh, mesh_done

    health, health_done, mesh, mesh_done = asyncio.run(scenario())
    assert mesh.status_code == 200 and health.status_code == 200
    # /health answered while the 1 s build was still running; a build on the
    # event loop would delay it past the build's end
    assert health_done < 0.7 and mesh_done >= 1.0


def test_mesh_link_failure_does_not_fail_request(monkeypatch, authed):
    client, fake_db = authed

    def broken_link(*args, **kwargs):
        raise RuntimeError("db down")

    monkeypatch.setattr(depth_router, "_build_mesh_sync", lambda image_base64: dict(FAKE_MESH))
    monkeypatch.setattr(depth_router.conversation_service, "store_mesh_reference", broken_link)

    resp = client.post(
        "/api/v1/depth/update-mesh",
        json={"image_base64": "aGVsbG8=", "conversation_id": "conv_1"},
    )
    assert resp.status_code == 200 and fake_db.rolled_back


def test_mesh_upload_keeps_http_errors(monkeypatch, authed):
    client, _ = authed

    def unavailable(image_base64):
        raise RuntimeError("PyTorch is not installed")

    monkeypatch.setattr(depth_router, "_build_mesh_sync", unavailable)
    files = {"image": ("room.jpg", b"jpeg-bytes", "image/jpeg")}
    resp = client.post("/api/v1/depth/generate-mesh/upload", files=files)
    assert resp.status_code == 503  # used to be converted to 500
    assert resp.json() == {"detail": "Depth service not available"}

    def crash(image_base64):
        raise ValueError("internal detail")

    monkeypatch.setattr(depth_router, "_build_mesh_sync", crash)
    resp = client.post("/api/v1/depth/generate-mesh/upload", files=files)
    assert resp.status_code == 500 and "internal detail" not in resp.text


def test_mesh_invalid_image_is_400(authed):
    client, _ = authed
    files = {"image": ("room.jpg", b"definitely not an image", "image/jpeg")}
    resp = client.post("/api/v1/depth/generate-mesh/upload", files=files)
    assert resp.status_code == 400


def test_mesh_size_limits(monkeypatch, authed):
    client, _ = authed
    monkeypatch.setattr(deps.settings, "max_file_size", 100)

    files = {"image": ("room.jpg", b"x" * 101, "image/jpeg")}
    assert client.post("/api/v1/depth/generate-mesh/upload", files=files).status_code == 413

    too_long = "A" * (deps.max_base64_length() + 1)
    resp = client.post("/api/v1/depth/generate-mesh", json={"image_base64": too_long})
    assert resp.status_code == 413


def test_generate_images_null_style_defaults_to_modern(monkeypatch, authed):
    client, _ = authed
    seen = {}

    async def fake_generate(**kwargs):
        seen.update(kwargs)
        return ["data:image/png;base64,AAAA"]

    monkeypatch.setattr(gemini_service, "generate_from_prompt", fake_generate)

    resp = client.post("/api/v1/images/generate", json={"prompt": "cozy room", "style": None})

    assert resp.status_code == 200, resp.text
    assert resp.json()["images"][0]["style"] == "modern"
    assert seen["style"] == "modern"


def test_images_errors_do_not_leak_internals(monkeypatch, authed):
    client, _ = authed

    async def failing(**kwargs):
        raise RuntimeError("secret upstream detail")

    monkeypatch.setattr(gemini_service, "generate_from_prompt", failing)
    resp = client.post("/api/v1/images/generate", json={"prompt": "cozy room"})
    assert resp.status_code == 500
    assert resp.json() == {"detail": "Image generation failed"}


def test_room_edit_llm_path_uses_json_mode(monkeypatch):
    assert "response_format" in inspect.signature(openai_service.chat_completion).parameters
    seen = {}

    async def fake_completion(messages, **kwargs):
        seen.update(kwargs)
        return '{"target": "wall", "property": "color", "value": "#001F3F"}'

    monkeypatch.setattr(rooms_router.openai_service, "chat_completion", fake_completion)
    edit = asyncio.run(rooms_router._parse_edit_request("Make the walls navy blue"))

    assert seen["response_format"] == {"type": "json_object"}
    assert edit == {"target": "wall", "property": "color", "value": "#001F3F"}


def test_room_edit_falls_back_on_unusable_llm_output(monkeypatch):
    async def fake_completion(messages, **kwargs):
        return '{"acknowledgment": "Sure!"}'

    monkeypatch.setattr(rooms_router.openai_service, "chat_completion", fake_completion)
    edit = asyncio.run(rooms_router._parse_edit_request("Make the walls white"))
    assert edit == {"target": "wall", "property": "color", "value": "#FFFFFF"}


# ============ Gemini edit retries ============

def _gemini_response(image: bool):
    part = SimpleNamespace(
        inline_data=SimpleNamespace(data=b"\x89PNG", mime_type="image/png") if image else None,
        text=None if image else "I can't do that",
    )
    return SimpleNamespace(candidates=[SimpleNamespace(content=SimpleNamespace(parts=[part]))])


def _fake_gemini_client(responses):
    calls = []

    async def generate_content(**kwargs):
        calls.append(kwargs)
        return responses[len(calls) - 1]

    client = SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(generate_content=generate_content)))
    return client, calls


def test_edit_room_backs_off_between_no_image_retries(monkeypatch):
    blocked = SimpleNamespace(candidates=None)  # e.g. safety block: no content at all
    client, calls = _fake_gemini_client([_gemini_response(False), blocked, _gemini_response(False)])
    delays = []

    async def fake_sleep(delay, *args, **kwargs):
        delays.append(delay)

    monkeypatch.setattr(gemini_service, "client", client)
    monkeypatch.setattr(gemini_module.asyncio, "sleep", fake_sleep)

    result = asyncio.run(gemini_service.edit_room("aGVsbG8=", "make the walls blue"))

    assert result == []
    assert len(calls) == 3
    assert delays == [1.5, 3.0]


def test_edit_room_returns_image_after_retry(monkeypatch):
    client, calls = _fake_gemini_client([_gemini_response(False), _gemini_response(True)])
    delays = []

    async def fake_sleep(delay, *args, **kwargs):
        delays.append(delay)

    monkeypatch.setattr(gemini_service, "client", client)
    monkeypatch.setattr(gemini_module.asyncio, "sleep", fake_sleep)

    result = asyncio.run(gemini_service.edit_room("aGVsbG8=", "make the walls blue"))

    assert result == ["data:image/png;base64,iVBORw=="]
    assert len(calls) == 2 and delays == [1.5]
