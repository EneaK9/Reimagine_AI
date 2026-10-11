"""
ReimagineAI - Upload size limit helper tests (app/deps.py)
"""
import asyncio
import base64
import math
import sys
from io import BytesIO
from pathlib import Path

import pytest
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.testclient import TestClient
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import deps  # noqa: E402
from app.deps import check_base64_size, max_base64_length, read_upload_limited  # noqa: E402

LIMIT = 1000


class CountingBytesIO(BytesIO):
    """BytesIO that records how many bytes were read in total."""

    def __init__(self, data: bytes):
        super().__init__(data)
        self.bytes_read = 0

    def read(self, size=-1):
        chunk = super().read(size)
        self.bytes_read += len(chunk)
        return chunk


def _read(upload: UploadFile, **kwargs) -> bytes:
    return asyncio.run(read_upload_limited(upload, **kwargs))


# ============ read_upload_limited ============

def test_upload_under_and_at_limit_returns_bytes():
    assert _read(UploadFile(file=BytesIO(b"x" * 10)), max_bytes=LIMIT) == b"x" * 10
    assert _read(UploadFile(file=BytesIO(b"y" * LIMIT)), max_bytes=LIMIT) == b"y" * LIMIT


def test_upload_over_limit_is_413_and_reads_at_most_limit_plus_one():
    stream = CountingBytesIO(b"z" * (LIMIT * 50))
    with pytest.raises(HTTPException) as err:
        _read(UploadFile(file=stream), max_bytes=LIMIT)  # size unknown -> read path
    assert err.value.status_code == 413
    assert stream.bytes_read <= LIMIT + 1


def test_upload_over_limit_rejected_from_recorded_size_without_reading():
    stream = CountingBytesIO(b"z" * (LIMIT + 1))
    with pytest.raises(HTTPException) as err:
        _read(UploadFile(file=stream, size=LIMIT + 1), max_bytes=LIMIT)
    assert err.value.status_code == 413
    assert stream.bytes_read == 0


def test_empty_upload_is_400():
    with pytest.raises(HTTPException) as err:
        _read(UploadFile(file=BytesIO(b"")), max_bytes=LIMIT)
    assert err.value.status_code == 400


def test_default_limit_is_settings_max_file_size(monkeypatch):
    monkeypatch.setattr(deps.settings, "max_file_size", 64)
    assert _read(UploadFile(file=BytesIO(b"a" * 64))) == b"a" * 64
    with pytest.raises(HTTPException) as err:
        _read(UploadFile(file=BytesIO(b"a" * 65)))
    assert err.value.status_code == 413


def test_multipart_upload_through_fastapi(monkeypatch):
    monkeypatch.setattr(deps.settings, "max_file_size", LIMIT)
    app = FastAPI()

    @app.post("/upload")
    async def upload(image: UploadFile = File(...)):
        return {"size": len(await read_upload_limited(image))}

    client = TestClient(app)
    ok = client.post("/upload", files={"image": ("a.jpg", b"1" * LIMIT, "image/jpeg")})
    assert ok.status_code == 200 and ok.json() == {"size": LIMIT}

    too_big = client.post("/upload", files={"image": ("a.jpg", b"1" * (LIMIT + 1), "image/jpeg")})
    assert too_big.status_code == 413
    assert "Maximum size" in too_big.json()["detail"]


# ============ check_base64_size ============

def test_base64_none_and_empty_pass():
    check_base64_size(None)
    check_base64_size("")


def test_base64_of_max_payload_passes_even_as_data_url():
    b64 = base64.b64encode(b"\xff" * LIMIT).decode()
    check_base64_size(b64, max_bytes=LIMIT)
    check_base64_size(f"data:image/jpeg;base64,{b64}", max_bytes=LIMIT)


def test_base64_over_limit_is_413():
    with pytest.raises(HTTPException) as err:
        check_base64_size("A" * (max_base64_length(LIMIT) + 1), max_bytes=LIMIT)
    assert err.value.status_code == 413


def test_default_base64_limit_covers_max_file_size():
    size = deps.settings.max_file_size
    encoded_len = 4 * math.ceil(size / 3)
    assert encoded_len <= max_base64_length() <= encoded_len + 2048
    with pytest.raises(HTTPException):
        check_base64_size("A" * (max_base64_length() + 1))


def test_base64_limit_in_json_endpoint(monkeypatch):
    monkeypatch.setattr(deps.settings, "max_file_size", LIMIT)
    app = FastAPI()

    class Body(BaseModel):
        image_base64: str

    @app.post("/json")
    async def json_endpoint(body: Body):
        check_base64_size(body.image_base64)
        return {"ok": True}

    client = TestClient(app)
    ok_b64 = base64.b64encode(b"\x00" * LIMIT).decode()
    assert client.post("/json", json={"image_base64": ok_b64}).status_code == 200
    too_big = "A" * (max_base64_length(LIMIT) + 1)
    assert client.post("/json", json={"image_base64": too_big}).status_code == 413
