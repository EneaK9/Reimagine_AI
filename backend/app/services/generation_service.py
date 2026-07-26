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

    # ---------- image -> GLB ----------

    async def image_to_glb(self, image: Image.Image, label: str = "") -> Optional[str]:
        """
        Generate a textured GLB from a furniture crop.
        Returns the API-relative URL of the stored GLB, or None on failure.
        """
        if not self.enabled:
            return None

        buf = BytesIO()
        image.convert("RGB").save(buf, "JPEG", quality=92)
        data_uri = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()

        try:
            async with httpx.AsyncClient(timeout=GENERATION_TIMEOUT_S) as client:
                response = await client.post(
                    f"https://fal.run/{settings.image_to_3d_model}",
                    headers={"Authorization": f"Key {settings.fal_api_key}"},
                    json={"image_url": data_uri},
                )
                response.raise_for_status()
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
