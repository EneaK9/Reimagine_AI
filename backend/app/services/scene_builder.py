"""
ReimagineAI - Scene Builder

Turns a single room photo into a structured, editable 3D scene:
1. Detect furniture + room info with Gemini (OpenAI vision fallback)
2. Estimate depth (reuses depth_service) to place objects in the room
3. Match each item to a procedural catalog asset
4. Assemble a SceneData document (room shell + per-object entries)

The result is intentionally a *good starting layout*, not a perfect
reconstruction — the mobile editor is where users fine-tune positions.
"""
from __future__ import annotations

import json
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ..config import get_settings
from ..models.scene import (
    AssetRef,
    MaterialDef,
    RoomShell,
    SceneData,
    SceneObject,
    Transform,
    WallFeature,
)
from .catalog_service import catalog_service
from .depth_service import depth_service
from .gemini_service import gemini_service
from .openai_service import openai_service

settings = get_settings()

DETECTION_PROMPT = """You are an interior-design vision system. Analyze this room photo.

Return ONLY valid JSON (no markdown fences) with this exact structure:
{
  "room_type": "living room",
  "style": "modern",
  "room_estimate": {"width_m": 4.0, "depth_m": 3.5, "height_m": 2.6},
  "wall_color": "#EDE8DF",
  "floor_color": "#A98B6D",
  "floor_type": "wood",
  "objects": [
    {
      "label": "grey fabric sofa",
      "category": "sofa",
      "bbox": [x_min, y_min, x_max, y_max],
      "color": "#8A8A8A",
      "width_m": 2.0,
      "against_wall": true
    }
  ],
  "features": [
    {"type": "window", "bbox": [x_min, y_min, x_max, y_max], "color": "#FFFFFF", "width_m": 1.5},
    {"type": "curtain", "bbox": [x_min, y_min, x_max, y_max], "color": "#8A8A8A", "width_m": 1.5},
    {"type": "door", "bbox": [x_min, y_min, x_max, y_max], "color": "#F0F0F0", "width_m": 0.9}
  ]
}

Rules:
- bbox is in pixel coordinates of THIS image (integers).
- category must be a simple generic furniture type: sofa, armchair, chair, table,
  coffee_table, desk, bed, nightstand, wardrobe, dresser, bookshelf, tv, tv_stand,
  lamp_floor, lamp_table, rug, plant, mirror, ottoman, sideboard.
- ONLY include free-standing furniture that sits on the floor (or on furniture,
  like a table lamp on a nightstand).
- DO include even partially visible or background items: potted plants,
  nightstands, side tables, table lamps, floor lamps, benches, poufs, rugs.
  Bedrooms usually have nightstands beside the bed — look carefully.
- Do NOT include: curtains, drapes, blinds, windows, doors, wall art, picture
  frames, posters, ceiling lights, pendant lamps, chandeliers, radiators,
  shelves mounted on walls, pillows, blankets, or anything attached to a wall
  or ceiling. These are part of the room, not furniture objects.
- width_m is your best real-world width estimate in meters.
- Include every piece of floor furniture you can find (max 15 objects).
- Ignore small decor (books, cups, frames).
- colors are hex approximations of the item's dominant color.
- features: windows, doors, and curtains go in "features" (NOT in objects),
  with their bboxes and dominant colors. Max 6 features.
"""


def _strip_json(text: str) -> str:
    """Remove markdown fences and grab the outermost JSON object."""
    text = text.strip()
    text = re.sub(r"^```(json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        return text[start:end + 1]
    return text


class SceneBuilder:
    async def detect_room(self, image_base64: str, image_size: Tuple[int, int]) -> Dict[str, Any]:
        """Run furniture/room detection; Gemini first, OpenAI vision fallback."""
        width, height = image_size
        prompt = DETECTION_PROMPT + f"\nThe image is {width}x{height} pixels."

        # --- Gemini (primary) ---
        if gemini_service.client:
            try:
                import base64 as b64
                from google.genai import types

                image_bytes = b64.b64decode(
                    image_base64.split(",")[1] if image_base64.startswith("data:") else image_base64
                )
                image_part = types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")
                response = gemini_service.client.models.generate_content(
                    model=settings.gemini_analysis_model,
                    contents=[prompt, image_part],
                    config=types.GenerateContentConfig(response_mime_type="application/json"),
                )
                return json.loads(_strip_json(response.text))
            except Exception as e:
                print(f"[SceneBuilder] Gemini detection failed, trying OpenAI: {e}")

        # --- OpenAI vision (fallback) ---
        try:
            response = await openai_service.client.chat.completions.create(
                model=settings.gpt_model,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {
                            "url": f"data:image/jpeg;base64,{image_base64}"
                        }},
                    ],
                }],
                max_tokens=2000,
            )
            return json.loads(_strip_json(response.choices[0].message.content))
        except Exception as e:
            raise RuntimeError(f"Furniture detection failed (Gemini and OpenAI): {e}")

    # ---------- placement ----------

    @staticmethod
    def _clamp(v: float, lo: float, hi: float) -> float:
        return max(lo, min(hi, v))

    def _place_objects(
        self,
        detected: List[Dict[str, Any]],
        depth_map: Optional[np.ndarray],
        image_size: Tuple[int, int],
        room: RoomShell,
    ) -> List[SceneObject]:
        """
        Map 2D detections into room coordinates.

        Convention: room centered at origin; x in [-w/2, w/2], z in [-d/2, d/2].
        The camera looks from +z toward -z, so the photo's back wall is at z=-d/2.
        MiDaS-style depth: higher value = closer to camera.
        """
        img_w, img_h = image_size
        objects: List[SceneObject] = []

        for det in detected[:15]:
            bbox = det.get("bbox") or [0, 0, img_w, img_h]
            try:
                x0, y0, x1, y1 = [float(v) for v in bbox]
            except (TypeError, ValueError):
                x0, y0, x1, y1 = 0.0, 0.0, float(img_w), float(img_h)
            x0, x1 = sorted((self._clamp(x0, 0, img_w), self._clamp(x1, 0, img_w)))
            y0, y1 = sorted((self._clamp(y0, 0, img_h), self._clamp(y1, 0, img_h)))
            if x1 - x0 < 4 or y1 - y0 < 4:
                continue

            entry = catalog_service.match(det.get("category", ""), det.get("width_m"))
            category = catalog_service.normalize_category(det.get("category", ""))
            if not entry:
                # No catalog match (curtains, windows, unknown labels...):
                # skip instead of rendering a meaningless box.
                print(f"[SceneBuilder] Skipping unmatched detection: "
                      f"{det.get('label')} ({det.get('category')})")
                continue
            dims = list(entry["dims_m"])
            asset_ref = entry["id"]

            # Horizontal position from bbox center
            cx_norm = ((x0 + x1) / 2.0) / img_w  # 0..1 left→right
            margin_x = dims[0] / 2.0 + 0.05
            pos_x = self._clamp(
                (cx_norm - 0.5) * room.width_m,
                -room.width_m / 2 + margin_x,
                room.width_m / 2 - margin_x,
            )

            # Depth position from mean depth inside the bbox (closer → larger z)
            closeness = 0.5
            if depth_map is not None:
                dh, dw = depth_map.shape
                bx0, bx1 = int(x0 / img_w * dw), max(int(x1 / img_w * dw), int(x0 / img_w * dw) + 1)
                by0, by1 = int(y0 / img_h * dh), max(int(y1 / img_h * dh), int(y0 / img_h * dh) + 1)
                patch = depth_map[by0:by1, bx0:bx1]
                if patch.size:
                    closeness = float(np.median(patch))

            margin_z = dims[2] / 2.0 + 0.05
            if det.get("against_wall"):
                pos_z = -room.depth_m / 2 + margin_z
            else:
                # closeness 1 (near camera) → front; 0 (far) → back wall
                pos_z = self._clamp(
                    (closeness - 0.5) * room.depth_m * 0.9,
                    -room.depth_m / 2 + margin_z,
                    room.depth_m / 2 - margin_z,
                )

            # Wall-adjacent items face into the room; others face the camera
            rot_y = 0.0 if not det.get("against_wall") else 0.0
            if det.get("against_wall") and pos_x < -room.width_m * 0.3:
                rot_y = 90.0   # left wall → face right
            elif det.get("against_wall") and pos_x > room.width_m * 0.3:
                rot_y = -90.0  # right wall → face left

            color = det.get("color") if isinstance(det.get("color"), str) else None
            obj = SceneObject(
                id=f"{category or 'item'}_{uuid.uuid4().hex[:6]}",
                category=category or "item",
                label=det.get("label") or (entry["name"] if entry else "Item"),
                asset=AssetRef(type="catalog", ref=asset_ref),
                transform=Transform(pos=[round(pos_x, 3), 0.0, round(pos_z, 3)], rot_y_deg=rot_y),
                dimensions_m=[round(d, 3) for d in dims],
                material_override=MaterialDef(color=color) if color else None,
                source={
                    "detected_from": "photo",
                    "bbox": [int(x0), int(y0), int(x1), int(y1)],
                    "raw_category": det.get("category"),
                },
            )
            objects.append(obj)

        self._resolve_overlaps(objects, room)
        return objects

    def _resolve_overlaps(self, objects: List[SceneObject], room: RoomShell) -> None:
        """Nudge overlapping footprints apart along x (a few passes is enough)."""
        for _ in range(3):
            moved = False
            for i in range(len(objects)):
                for j in range(i + 1, len(objects)):
                    a, b = objects[i], objects[j]
                    if a.category == "rug" or b.category == "rug":
                        continue  # rugs live under other furniture
                    ax, az = a.transform.pos[0], a.transform.pos[2]
                    bx, bz = b.transform.pos[0], b.transform.pos[2]
                    half_w = (a.dimensions_m[0] + b.dimensions_m[0]) / 2
                    half_d = (a.dimensions_m[2] + b.dimensions_m[2]) / 2
                    dx, dz = bx - ax, bz - az
                    if abs(dx) < half_w and abs(dz) < half_d:
                        push = (half_w - abs(dx)) / 2 + 0.05
                        direction = 1.0 if dx >= 0 else -1.0
                        limit = room.width_m / 2 - 0.1
                        a.transform.pos[0] = self._clamp(ax - direction * push, -limit, limit)
                        b.transform.pos[0] = self._clamp(bx + direction * push, -limit, limit)
                        moved = True
            if not moved:
                break

    def _place_features(
        self,
        detected: List[Dict[str, Any]],
        image_size: Tuple[int, int],
        room: RoomShell,
    ) -> List[WallFeature]:
        """Map detected windows/doors/curtains onto the room walls."""
        img_w, img_h = image_size
        defaults = {
            "window": {"bottom_m": 0.8, "height_m": 1.3, "color": "#EAF2F8"},
            "door": {"bottom_m": 0.0, "height_m": 2.0, "color": "#EFEBE2"},
            "curtain": {"bottom_m": 0.05, "height_m": room.height_m - 0.2, "color": "#B9B2A6"},
        }
        features: List[WallFeature] = []
        for det in detected[:6]:
            ftype = (det.get("type") or "").strip().lower()
            if ftype not in defaults:
                continue
            bbox = det.get("bbox") or [0, 0, img_w, img_h]
            try:
                x0, y0, x1, y1 = [float(v) for v in bbox]
            except (TypeError, ValueError):
                continue
            cx_norm = ((x0 + x1) / 2.0) / img_w

            # Which wall? Extreme left/right of the frame -> side walls,
            # otherwise the back wall (the one facing the camera).
            if cx_norm < 0.15:
                wall, wall_len = "left", room.depth_m
                center_x = 0.0
            elif cx_norm > 0.85:
                wall, wall_len = "right", room.depth_m
                center_x = 0.0
            else:
                wall, wall_len = "back", room.width_m
                center_x = (cx_norm - 0.5) * room.width_m

            d = defaults[ftype]
            width = float(det.get("width_m") or ((x1 - x0) / img_w) * wall_len)
            width = self._clamp(width, 0.4, wall_len - 0.2)
            height = self._clamp(float(det.get("height_m") or d["height_m"]), 0.4, room.height_m - 0.1)
            bottom = self._clamp(float(det.get("bottom_m") or d["bottom_m"]), 0.0, room.height_m - height)
            center_x = self._clamp(center_x, -wall_len / 2 + width / 2, wall_len / 2 - width / 2)

            features.append(WallFeature(
                id=f"{ftype}_{uuid.uuid4().hex[:6]}",
                type=ftype,
                wall=wall,
                center_x_m=round(center_x, 3),
                width_m=round(width, 3),
                height_m=round(height, 3),
                bottom_m=round(bottom, 3),
                color=det.get("color") or d["color"],
            ))
        return features

    # ---------- main entry ----------

    async def build_scene_from_image(self, image_base64: str):
        # Depth map (best-effort; placement degrades gracefully without it).
        # Detection runs on the SAME resized image so bboxes and depth line up.
        depth_map = None
        try:
            depth_map, resized_image = depth_service.generate_depth_map_v2(image_base64)
        except Exception as e:
            print(f"[SceneBuilder] Depth estimation unavailable, using layout-only placement: {e}")
            resized_image = depth_service._decode_base64_image(image_base64)
            w, h = resized_image.size
            if max(w, h) > 768:
                scale = 768 / max(w, h)
                resized_image = resized_image.resize((int(w * scale), int(h * scale)))

        image_size = resized_image.size  # (w, h)
        detection_base64 = depth_service._encode_image_base64(resized_image, "JPEG")
        detection = await self.detect_room(detection_base64, image_size)

        est = detection.get("room_estimate") or {}
        room = RoomShell(
            width_m=self._clamp(float(est.get("width_m") or 4.0), 2.0, 10.0),
            depth_m=self._clamp(float(est.get("depth_m") or 3.5), 2.0, 10.0),
            height_m=self._clamp(float(est.get("height_m") or 2.6), 2.2, 4.0),
            wall_material=MaterialDef(color=detection.get("wall_color") or "#F2EDE4"),
            floor_material=MaterialDef(
                color=detection.get("floor_color") or "#A98B6D",
                texture=detection.get("floor_type"),
            ),
        )

        room.features = self._place_features(
            detection.get("features") or [], image_size, room
        )

        # NOTE: detection bboxes are relative to the image we described in the prompt;
        # depth map is the same size, so coordinates line up.
        objects = self._place_objects(
            detection.get("objects") or [], depth_map, image_size, room
        )

        data = SceneData(
            room_type=detection.get("room_type") or "room",
            style=detection.get("style"),
            room=room,
            objects=objects,
        )
        # Return the resized photo too so the caller can persist it
        # (needed later to crop per-object images for 3D generation).
        return data, resized_image


scene_builder = SceneBuilder()
