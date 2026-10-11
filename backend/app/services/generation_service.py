"""
ReimagineAI - Image-to-3D Generation Service

Turns a cropped furniture photo into a real textured GLB mesh using a
hosted image-to-3D model (fal.ai TRELLIS by default). This is what makes
the editable scene look like *the user's* furniture instead of the
procedural stand-ins.

Disabled gracefully when FAL_API_KEY is not configured.
"""
from __future__ import annotations

import base64
import os
import uuid
from dataclasses import dataclass
from io import BytesIO
from typing import Optional

import httpx
import numpy as np
from PIL import Image

from ..config import get_settings

settings = get_settings()

GENERATION_TIMEOUT_S = 420  # queue wait + TRELLIS.2 (~20-60 s) + GLB baking


@dataclass
class GeneratedMesh:
    url: str                           # API-relative URL of the stored GLB
    path: str                          # local file path
    alpha: Optional[np.ndarray] = None  # object mask in original crop pixels (for alignment)


class GenerationService:
    def __init__(self):
        data_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data")
        self.generated_dir = os.path.join(data_dir, "generated")
        self.scene_images_dir = os.path.join(data_dir, "scene_images")
        os.makedirs(self.generated_dir, exist_ok=True)
        os.makedirs(self.scene_images_dir, exist_ok=True)

    @property
    def enabled(self) -> bool:
        return bool(settings.fal_api_key)

    # ---------- scene photo persistence ----------

    def save_scene_image(self, scene_id: str, image: Image.Image) -> str:
        path = os.path.join(self.scene_images_dir, f"{scene_id}.jpg")
        image.convert("RGB").save(path, "JPEG", quality=90)
        return path

    def load_scene_image(self, scene_id: str) -> Optional[Image.Image]:
        path = os.path.join(self.scene_images_dir, f"{scene_id}.jpg")
        if not os.path.exists(path):
            return None
        return Image.open(path).convert("RGB")

    # ---------- generated asset files ----------

    def asset_path(self, filename: str) -> Optional[str]:
        # Serve only files we created (no path traversal)
        safe = os.path.basename(filename)
        path = os.path.join(self.generated_dir, safe)
        return path if os.path.exists(path) else None

    def save_texture(self, image: Image.Image, kind: str = "tex") -> str:
        """Store a texture patch sampled from the photo; returns its URL path."""
        filename = f"{kind}_{uuid.uuid4().hex[:10]}.jpg"
        image.convert("RGB").save(
            os.path.join(self.generated_dir, filename), "JPEG", quality=88
        )
        return f"/api/v1/scenes/assets/{filename}"

    # ---------- image -> GLB ----------

    _rembg_sessions: dict = {}

    def _rembg_session(self, model_name: str):
        if model_name not in self._rembg_sessions:
            from rembg import new_session

            print(f"[Gen3D] Loading segmentation model '{model_name}'...")
            self._rembg_sessions[model_name] = new_session(model_name)
        return self._rembg_sessions[model_name]

    def _remove_background(self, image: Image.Image, label: str) -> Optional[Image.Image]:
        """
        Cut the furniture out of its crop. Without this, the image-to-3D
        model reconstructs the room background as part of the mesh
        (result: object embedded in a dark slab). Tries the fast u2net
        model first, then the stronger isnet for hard cases (dark objects
        on dark backgrounds). Returns None when both fail — sending a raw
        crop produces slab meshes, so the caller keeps the procedural model.
        """
        try:
            from rembg import remove

            import numpy as np

            for model_name in ("u2net", "isnet-general-use"):
                try:
                    cut = remove(image.convert("RGB"), session=self._rembg_session(model_name))
                except Exception as e:
                    print(f"[Gen3D] Segmentation model {model_name} failed for '{label}': {e}")
                    continue
                alpha = np.asarray(cut.getchannel("A"))
                coverage = float((alpha > 30).mean())
                if coverage >= 0.05:
                    return cut
                print(f"[Gen3D] {model_name} left too little of '{label}' "
                      f"({coverage:.0%}); trying next model")

            print(f"[Gen3D] Background removal failed for '{label}' — keeping procedural model")
            return None
        except ImportError:
            print("[Gen3D] rembg not installed — sending raw crop (pip install rembg)")
            return image
        except Exception as e:
            print(f"[Gen3D] Background removal failed for '{label}' — keeping procedural: {e}")
            return None

    MIN_CROP_PX = 40       # below this the crop carries no usable detail
    TARGET_CROP_PX = 512   # upscale small crops so segmentation + 3D work well

    def _prepare_crop(self, image: Image.Image, label: str) -> Optional[Image.Image]:
        """Reject hopeless crops; upscale small ones before segmentation."""
        if min(image.width, image.height) < self.MIN_CROP_PX:
            print(f"[Gen3D] Crop for '{label}' too small "
                  f"({image.width}x{image.height}) — keeping procedural model")
            return None
        if min(image.width, image.height) < self.TARGET_CROP_PX:
            scale = self.TARGET_CROP_PX / min(image.width, image.height)
            image = image.resize(
                (int(image.width * scale), int(image.height * scale)),
                Image.Resampling.LANCZOS,
            )
        return image

    def _gemini_isolate(self, image: Image.Image, label: str) -> Optional[Image.Image]:
        """
        Last-resort isolation: ask Gemini's image model to redraw the object
        alone on a white background — handles occlusion and dark-on-dark
        cases where segmentation fails, so the object can still be generated.
        """
        try:
            from google.genai import types

            from .gemini_service import gemini_service

            if not gemini_service.client:
                return None

            buf = BytesIO()
            image.convert("RGB").save(buf, "JPEG", quality=90)
            prompt = (
                f"Extract the {label} from this photo. Output an image showing ONLY "
                f"the {label}, complete and fully visible, centered on a pure white "
                f"background. Keep its exact shape, colors, materials and proportions. "
                f"Complete any parts that are hidden behind other objects."
            )
            response = gemini_service.client.models.generate_content(
                model=settings.gemini_model,
                contents=[prompt, types.Part.from_bytes(data=buf.getvalue(), mime_type="image/jpeg")],
                config=types.GenerateContentConfig(response_modalities=["TEXT", "IMAGE"]),
            )
            for part in response.candidates[0].content.parts:
                if part.inline_data is not None:
                    return Image.open(BytesIO(part.inline_data.data)).convert("RGB")
        except Exception as e:
            print(f"[Gen3D] Gemini isolation failed for '{label}': {e}")
        return None

    def _request_body(self, data_uri: str) -> dict:
        body = {"image_url": data_uri}
        if "trellis-2" in settings.image_to_3d_model:
            # fal's defaults (500k faces, 2K textures) give ~18 MB GLBs, 93% of
            # it geometry. TRELLIS.2 simplifies *before* baking textures, so a
            # lower face budget stays clean and loads fast on phones.
            texture = min((1024, 2048, 4096), key=lambda v: abs(v - int(settings.image_to_3d_texture)))
            body.update({
                "resolution": 1024,
                "decimation_target": int(min(2_000_000, max(5_000, settings.image_to_3d_faces))),
                "texture_size": texture,  # fal accepts 1024 / 2048 / 4096 only
            })
        return body

    @staticmethod
    def _mesh_url(result: dict) -> Optional[str]:
        """GLB URL from a fal result (keys differ between 3D models)."""
        candidates = [result.get("model_glb"), (result.get("model_urls") or {}).get("glb"),
                      result.get("model_mesh"), result.get("glb"), result.get("mesh")]
        for entry in candidates:
            if isinstance(entry, dict) and entry.get("url"):
                return entry["url"]
            if isinstance(entry, str) and entry.startswith("http"):
                return entry
        return None

    async def _run_fal(self, client: httpx.AsyncClient, body: dict, label: str) -> Optional[dict]:
        """
        fal queue API: submit, poll the status URL, fetch the result. Unlike
        a single synchronous call, a dropped connection doesn't lose the job.
        """
        import asyncio
        import time

        headers = {"Authorization": f"Key {settings.fal_api_key}"}
        submit = None
        for attempt in range(3):
            submit = await client.post(
                f"https://queue.fal.run/{settings.image_to_3d_model}", headers=headers, json=body,
            )
            if submit.status_code in (403, 429) and attempt < 2:
                wait = 10 * (attempt + 1)  # concurrency / rate limit
                print(f"[Gen3D] fal returned {submit.status_code} for '{label}'; retrying in {wait}s")
                await asyncio.sleep(wait)
                continue
            break
        if submit.status_code >= 400:
            print(f"[Gen3D] fal submit error {submit.status_code} for '{label}': {submit.text[:300]}")
            return None
        job = submit.json()
        status_url, response_url = job.get("status_url"), job.get("response_url")
        if not status_url or not response_url:
            return job if self._mesh_url(job) else None  # synchronous-style answer

        deadline = time.monotonic() + GENERATION_TIMEOUT_S
        delay = 2.0
        server_errors = 0
        while time.monotonic() < deadline:
            await asyncio.sleep(delay)
            delay = min(delay * 1.4, 8.0)
            try:
                status = await client.get(status_url, headers=headers)
            except httpx.HTTPError as e:
                print(f"[Gen3D] status poll failed for '{label}' ({e!r}); retrying")
                continue
            if status.status_code == 429 or status.status_code >= 500:
                server_errors += 1
                if server_errors <= 5:
                    continue  # transient
            if status.status_code >= 400:
                print(f"[Gen3D] fal status error {status.status_code} for '{label}': {status.text[:200]}")
                await self._cancel(client, job, headers)
                return None
            state = status.json().get("status")
            if state == "COMPLETED":
                result = await client.get(response_url, headers=headers)
                if result.status_code >= 400:
                    print(f"[Gen3D] fal result error {result.status_code} for '{label}': {result.text[:300]}")
                    return None
                return result.json()
            if state not in ("IN_QUEUE", "IN_PROGRESS"):
                print(f"[Gen3D] fal job for '{label}' ended with status {state}")
                return None
        print(f"[Gen3D] fal job for '{label}' timed out after {GENERATION_TIMEOUT_S}s")
        await self._cancel(client, job, headers)  # stop paying for a result nobody waits for
        return None

    @staticmethod
    async def _cancel(client: httpx.AsyncClient, job: dict, headers: dict) -> None:
        url = job.get("cancel_url")
        if not url:
            return
        try:
            await client.put(url, headers=headers)
        except httpx.HTTPError:
            pass

    async def image_to_glb(self, image: Image.Image, label: str = "") -> Optional[GeneratedMesh]:
        """
        Generate a textured GLB from a furniture crop. Returns the stored mesh
        (plus the object's cut-out mask for alignment), or None on failure.
        """
        if not self.enabled:
            return None

        import asyncio

        prepared = self._prepare_crop(image, label)
        if prepared is None:
            return None

        # Background removal is CPU-bound; keep it off the event loop
        cut = await asyncio.to_thread(self._remove_background, prepared, label)
        alpha = None
        if cut is not None and cut.mode == "RGBA":
            # Mask back in the original crop's pixels (prepared may be upscaled)
            alpha = np.asarray(cut.getchannel("A").resize(image.size, Image.Resampling.BILINEAR)) > 127
        if cut is None:
            # Segmentation failed (occluded / dark-on-dark): have Gemini
            # redraw the object clean on white, then generate from that.
            cut = await asyncio.to_thread(self._gemini_isolate, prepared, label)
            if cut is None:
                return None
            print(f"[Gen3D] Used Gemini isolation for '{label}'")

        buf = BytesIO()
        if cut.mode == "RGBA":
            cut.save(buf, "PNG")
            data_uri = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
        else:
            cut.convert("RGB").save(buf, "JPEG", quality=92)
            data_uri = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()

        try:
            async with httpx.AsyncClient(timeout=60) as client:
                result = await self._run_fal(client, self._request_body(data_uri), label)
                if not result:
                    return None
                mesh_url = self._mesh_url(result)
                if not mesh_url:
                    print(f"[Gen3D] No mesh URL in response for '{label}': {list(result.keys())}")
                    return None
                glb = await client.get(mesh_url, timeout=120)
                glb.raise_for_status()
            if not glb.content.startswith(b"glTF"):
                print(f"[Gen3D] Result for '{label}' is not a GLB file — ignoring")
                return None

            filename = f"gen_{uuid.uuid4().hex[:12]}.glb"
            path = os.path.join(self.generated_dir, filename)
            with open(path, "wb") as f:
                f.write(glb.content)
            print(f"[Gen3D] Generated {filename} for '{label}' ({len(glb.content)//1024} KB)")
            return GeneratedMesh(url=f"/api/v1/scenes/assets/{filename}", path=path, alpha=alpha)

        except Exception as e:
            print(f"[Gen3D] Generation failed for '{label}': {e!r}")
            return None


generation_service = GenerationService()
