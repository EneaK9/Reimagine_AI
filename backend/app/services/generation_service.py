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
from io import BytesIO
from typing import Optional

import httpx
from PIL import Image

from ..config import get_settings

settings = get_settings()

GENERATION_TIMEOUT_S = 240  # TRELLIS runs ~20-60s; leave headroom for queueing


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

    async def image_to_glb(self, image: Image.Image, label: str = "") -> Optional[str]:
        """
        Generate a textured GLB from a furniture crop.
        Returns the API-relative URL of the stored GLB, or None on failure.
        """
        if not self.enabled:
            return None

        import asyncio

        prepared = self._prepare_crop(image, label)
        if prepared is None:
            return None

        # Background removal is CPU-bound; keep it off the event loop
        cut = await asyncio.to_thread(self._remove_background, prepared, label)
        if cut is None:
            return None

        buf = BytesIO()
        if cut.mode == "RGBA":
            cut.save(buf, "PNG")
            data_uri = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
        else:
            cut.convert("RGB").save(buf, "JPEG", quality=92)
            data_uri = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()

        try:
            async with httpx.AsyncClient(timeout=GENERATION_TIMEOUT_S) as client:
                response = None
                for attempt in range(3):
                    response = await client.post(
                        f"https://fal.run/{settings.image_to_3d_model}",
                        headers={"Authorization": f"Key {settings.fal_api_key}"},
                        json={"image_url": data_uri},
                    )
                    if response.status_code in (403, 429) and attempt < 2:
                        # Concurrency/rate limit — back off and retry
                        wait = 10 * (attempt + 1)
                        print(f"[Gen3D] fal returned {response.status_code} for "
                              f"'{label}' ({response.text[:150]}); retrying in {wait}s")
                        await asyncio.sleep(wait)
                        continue
                    break
                if response.status_code >= 400:
                    print(f"[Gen3D] fal error {response.status_code} for '{label}': "
                          f"{response.text[:300]}")
                    return None
                result = response.json()

                # fal model outputs vary slightly; check the common keys
                mesh_url = None
                for key in ("model_mesh", "model_glb", "mesh", "glb"):
                    entry = result.get(key)
                    if isinstance(entry, dict) and entry.get("url"):
                        mesh_url = entry["url"]
                        break
                    if isinstance(entry, str) and entry.startswith("http"):
                        mesh_url = entry
                        break
                if not mesh_url:
                    print(f"[Gen3D] No mesh URL in response for '{label}': {list(result.keys())}")
                    return None

                glb = await client.get(mesh_url)
                glb.raise_for_status()

            filename = f"gen_{uuid.uuid4().hex[:12]}.glb"
            with open(os.path.join(self.generated_dir, filename), "wb") as f:
                f.write(glb.content)
            print(f"[Gen3D] Generated {filename} for '{label}' ({len(glb.content)//1024} KB)")
            return f"/api/v1/scenes/assets/{filename}"

        except Exception as e:
            print(f"[Gen3D] Generation failed for '{label}': {e}")
            return None


generation_service = GenerationService()
