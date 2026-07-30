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
  "wall_sample_bbox": [x_min, y_min, x_max, y_max],
  "floor_sample_bbox": [x_min, y_min, x_max, y_max],
  "objects": [
    {
      "label": "grey fabric sofa",
      "category": "sofa",
      "bbox": [x_min, y_min, x_max, y_max],
      "color": "#8A8A8A",
      "width_m": 2.0,
      "against_wall": true,
      "plan_pos": {"x_m": 0.4, "z_m": -1.2, "rot_y_deg": 0},
      "relations": [
        {"type": "against", "target": "back_wall"},
        {"type": "beside", "target": 0, "side": "right"},
        {"type": "on", "target": 2},
        {"type": "in_front_of", "target": 0},
        {"type": "under", "target": "window"}
      ]
    }
  ],
  "features": [
    {"type": "window", "style": "floor_to_ceiling", "bbox": [x_min, y_min, x_max, y_max], "color": "#FFFFFF", "width_m": 1.5},
    {"type": "curtain", "style": "sheer", "bbox": [x_min, y_min, x_max, y_max], "color": "#8A8A8A", "width_m": 1.5},
    {"type": "door", "bbox": [x_min, y_min, x_max, y_max], "color": "#F0F0F0", "width_m": 0.9},
    {"type": "art", "bbox": [x_min, y_min, x_max, y_max], "color": "#D8D2C4", "width_m": 0.5},
    {"type": "pendant", "bbox": [x_min, y_min, x_max, y_max], "color": "#E8E4DA", "width_m": 0.35},
    {"type": "mirror", "bbox": [x_min, y_min, x_max, y_max], "color": "#C3D3DC", "width_m": 0.6}
  ]
}

Rules:
- bbox is in pixel coordinates of THIS image (integers).
- category must be a simple generic furniture type: sofa, armchair, chair, table,
  coffee_table, desk, bed, nightstand, wardrobe, dresser, bookshelf, tv, tv_stand,
  lamp_floor, lamp_table, rug, plant, mirror, ottoman, sideboard, console, bench,
  stool, fridge, stove, kitchen_cabinet, kitchen_island, sink, toilet, bathtub,
  shower, washing_machine. Works for ANY room: kitchen, bathroom, office, hallway.
- ONLY include free-standing furniture that sits on the floor (or on furniture,
  like a table lamp on a nightstand).
- Be EXHAUSTIVE: list EVERY piece of floor furniture, including partially
  visible or background items: potted plants, nightstands, side tables,
  table lamps, floor lamps, benches, poufs, rugs. If the same item appears
  twice (e.g. TWO nightstands, TWO lamps), output a separate entry for EACH.
  Bedrooms usually have a nightstand on each side of the bed — look carefully.
- Do NOT put in objects: curtains, windows, doors, wall art, pendant lights,
  chandeliers, radiators, wall shelves, pillows, blankets — anything attached
  to a wall or ceiling belongs in "features" or nowhere.
- width_m is your best real-world width estimate in meters.
- relations describe HOW objects are positioned relative to each other —
  this is what makes the 3D layout match the photo. Use them generously:
  * {"type": "against", "target": "back_wall"|"left_wall"|"right_wall"} —
    the object touches that wall (back wall = the one facing the camera).
  * {"type": "beside", "target": <objects array index>, "side": "left"|"right"} —
    touching/adjacent to another object (nightstand beside bed).
  * {"type": "on", "target": <objects array index>} — sitting ON TOP of
    another object (table lamp on a nightstand, TV on a tv_stand).
  * {"type": "in_front_of", "target": <objects array index>} — directly in
    front of it (coffee table in front of sofa).
  * {"type": "under", "target": "window"|"mirror"|"art"|"pendant"} — directly
    below that wall/ceiling feature (console under the mirror).
  Targets are 0-based indices into this same objects array.
- EVERY object MUST have at least one relation — look at the photo and state
  where each thing stands relative to walls and other furniture.
- plan_pos: draw a TOP-DOWN FLOOR PLAN of the room in your head and give each
  object's center position in meters. Coordinate system: origin at the room
  center. x runs left (-width/2) to right (+width/2) as seen in the photo.
  z runs from the back wall (-depth/2, the wall facing the camera) to the
  camera (+depth/2). rot_y_deg: 0 = the object's front faces the camera,
  90 = faces the right wall, -90 = faces the left wall, 180 = faces the back
  wall. Be consistent with your room_estimate dimensions. This is the most
  important field for placing objects correctly — take your time with it.
- Max 20 objects.
- Ignore tiny decor (books, cups, vases).
- colors are hex approximations of the item's dominant color.
- wall_sample_bbox: a rectangular patch showing ONLY bare wall (no furniture,
  no art, no windows, no strong shadows) — used to sample the wall material.
- floor_sample_bbox: a rectangular patch showing ONLY bare floor — used to
  sample the floor material. Pick the cleanest, most evenly lit areas.
- features: windows, doors, curtains, framed wall art / picture groups
  ("art"), hanging ceiling lights ("pendant"), and WALL-MOUNTED mirrors
  ("mirror") go in "features" with their bboxes and dominant colors.
- windows have a "style": "standard" (normal window), "floor_to_ceiling"
  (glass from floor to ceiling), or "sliding_door" (glass door to balcony/
  garden). curtains have "style": "sheer" (translucent voile) or "solid".
  Only report windows/doors/curtains that are actually visible in the photo.
  A freestanding mirror on the floor is an OBJECT; a mirror hanging on the
  wall is a FEATURE. A group of small frames close together = one "art"
  feature with a bbox around the whole group. Max 10 features.
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
    def __init__(self):
        self._working_gemini_model: str | None = None

    # ---------- provider-agnostic vision analysis ----------

    async def _openai_json(self, prompt: str, image_base64: str) -> Dict[str, Any]:
        """Ask OpenAI's vision model for a JSON analysis of the photo."""
        response = await openai_service.client.chat.completions.create(
            model=settings.openai_vision_model,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {
                        "url": f"data:image/jpeg;base64,{image_base64}"
                    }},
                ],
            }],
            response_format={"type": "json_object"},
        )
        return json.loads(_strip_json(response.choices[0].message.content))

    def _gemini_json(self, prompt: str, image_base64: str) -> Optional[Dict[str, Any]]:
        """Ask Gemini for a JSON analysis (model-name cascade survives retirements)."""
        if not gemini_service.client:
            return None
        import base64 as b64
        from google.genai import types

        image_bytes = b64.b64decode(
            image_base64.split(",")[1] if image_base64.startswith("data:") else image_base64
        )
        image_part = types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")
        candidates = list(dict.fromkeys([
            self._working_gemini_model or settings.gemini_analysis_model,
            settings.gemini_analysis_model,
            "gemini-flash-latest",
            "gemini-3-flash-preview",
            "gemini-2.5-flash",
            "gemini-2.0-flash",
        ]))
        last_error: Optional[Exception] = None
        for model in candidates:
            if not model:
                continue
            try:
                response = gemini_service.client.models.generate_content(
                    model=model,
                    contents=[prompt, image_part],
                    config=types.GenerateContentConfig(response_mime_type="application/json"),
                )
                result = json.loads(_strip_json(response.text))
                if self._working_gemini_model != model:
                    print(f"[SceneBuilder] Using Gemini model: {model}")
                    self._working_gemini_model = model
                return result
            except Exception as e:
                last_error = e
                if any(k in str(e) for k in ("NOT_FOUND", "not found", "404")):
                    print(f"[SceneBuilder] Gemini model {model} unavailable, trying next")
                    continue
                break
        if last_error:
            raise last_error
        return None

    async def _ask_json(self, prompt: str, image_base64: str) -> Dict[str, Any]:
        """
        Run a vision->JSON query on the configured provider, falling back
        to the other one. The provider order comes from settings
        (scene_analysis_provider: "openai" | "gemini").
        """
        order = (
            ["openai", "gemini"]
            if settings.scene_analysis_provider.lower() == "openai"
            else ["gemini", "openai"]
        )
        last_error: Optional[Exception] = None
        for provider in order:
            try:
                if provider == "openai":
                    return await self._openai_json(prompt, image_base64)
                result = self._gemini_json(prompt, image_base64)
                if result is not None:
                    return result
            except Exception as e:
                last_error = e
                print(f"[SceneBuilder] {provider} analysis failed, trying next provider: {e}")
        raise RuntimeError(f"Room analysis failed on all providers: {last_error}")

    async def detect_room(self, image_base64: str, image_size: Tuple[int, int]) -> Dict[str, Any]:
        """Run furniture/room detection on the configured vision provider."""
        width, height = image_size
        prompt = DETECTION_PROMPT + f"\nThe image is {width}x{height} pixels."
        return await self._ask_json(prompt, image_base64)

    async def refine_detection(
        self,
        image_base64: str,
        image_size: Tuple[int, int],
        first_pass: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Understanding layer: a second look at the photo WITH the first
        analysis in hand. Catches missed objects, wrong window styles,
        wrong walls, and bad size estimates. Falls back to the first pass.
        """
        width, height = image_size
        prompt = f"""You are reviewing a room analysis for a 3D reconstruction.

Here is the photo ({width}x{height} px) and a first-pass analysis of it:

{json.dumps(first_pass, indent=1)}

Carefully compare the analysis against the photo and return the CORRECTED
full JSON in the exact same schema. Check specifically:
1. MISSED furniture: nightstands, lamps, plants, stools, side tables —
   anything on the floor that is not yet in "objects". Add them with bboxes.
2. Window style: is it really "standard", or is it floor_to_ceiling glazing
   or a sliding door? Are curtains sheer or solid? Fix "style" fields.
3. Wrong entries: remove objects that are actually part of another object
   (pillows on a bed) or that do not exist in the photo.
4. Sizes: fix clearly wrong width_m estimates (a bed is ~1.4-2.0m wide,
   a nightstand ~0.4-0.6m).
5. room_estimate, wall/floor colors and sample bboxes: adjust if wrong.
6. plan_pos: mentally draw the top-down floor plan and verify each object's
   x_m/z_m matches where it stands in the photo (origin = room center,
   back wall at z=-depth/2). Fix any object that would end up on the wrong
   side of the room or overlapping another object's footprint.

Return ONLY the corrected JSON, same schema, no commentary."""

        try:
            refined = await self._ask_json(prompt, image_base64)
            # Sanity: a valid refinement must keep the core keys
            if isinstance(refined, dict) and "objects" in refined:
                n_before = len(first_pass.get("objects") or [])
                n_after = len(refined.get("objects") or [])
                print(f"[SceneBuilder] Refinement pass: {n_before} -> {n_after} objects")
                return refined
        except Exception as e:
            print(f"[SceneBuilder] Refinement pass failed (using first pass): {e}")
        return first_pass

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
        placed: List[tuple] = []  # (detection_index, SceneObject, det) for relations

        for det_idx, det in enumerate(detected[:20]):
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
            # Size the object from the photo, not the catalog default:
            # scale footprint by the detected real-world width.
            det_width = det.get("width_m")
            if det_width:
                ratio = self._clamp(float(det_width) / dims[0], 0.6, 1.6)
                dims = [round(dims[0] * ratio, 3), dims[1], round(dims[2] * ratio, 3)]

            # Horizontal position from bbox center
            cx_norm = ((x0 + x1) / 2.0) / img_w  # 0..1 left→right
            margin_x = dims[0] / 2.0 + 0.05
            pos_x = self._clamp(
                (cx_norm - 0.5) * room.width_m,
                -room.width_m / 2 + margin_x,
                room.width_m / 2 - margin_x,
            )

            # Depth position (closer → larger z). Sample the BOTTOM strip of
            # the bbox — that's where the object touches the floor; the full
            # bbox includes background wall for tall/thin objects. Blend with
            # the vertical image position (lower in frame = closer to camera).
            closeness = 0.5
            if depth_map is not None:
                dh, dw = depth_map.shape
                bx0, bx1 = int(x0 / img_w * dw), max(int(x1 / img_w * dw), int(x0 / img_w * dw) + 1)
                strip_top = int((y1 - (y1 - y0) * 0.25) / img_h * dh)
                by1 = max(int(y1 / img_h * dh), strip_top + 1)
                patch = depth_map[strip_top:by1, bx0:bx1]
                if patch.size:
                    depth_closeness = float(np.median(patch))
                    y_prior = self._clamp(y1 / img_h, 0.0, 1.0)
                    closeness = 0.65 * depth_closeness + 0.35 * y_prior

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

            # The model's own floor-plan coordinates are the PRIMARY placement
            # signal — it reads the photo's layout better than bbox+depth
            # trigonometry. Depth math above remains the fallback.
            plan = det.get("plan_pos") or {}
            try:
                px, pz = float(plan["x_m"]), float(plan["z_m"])
                if abs(px) <= room.width_m / 2 + 0.5 and abs(pz) <= room.depth_m / 2 + 0.5:
                    pos_x = self._clamp(px, -room.width_m / 2 + margin_x, room.width_m / 2 - margin_x)
                    pos_z = self._clamp(pz, -room.depth_m / 2 + margin_z, room.depth_m / 2 - margin_z)
                    if "rot_y_deg" in plan:
                        rot_y = float(plan["rot_y_deg"]) % 360
            except (KeyError, TypeError, ValueError):
                pass

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
                    "img_size": [img_w, img_h],  # bbox coordinate space
                    "raw_category": det.get("category"),
                },
            )
            objects.append(obj)
            placed.append((det_idx, obj, det))

        # Relationship constraints: snap objects into the arrangements the
        # photo shows (beside/on/against/in-front-of/under). Two passes so
        # chains resolve (lamp ON nightstand which is BESIDE the bed).
        by_det_index = {i: o for i, o, _ in placed}
        linked: set = set()
        pinned: set = set()

        # Safety net FIRST: some furniture practically always stands against
        # a wall. If the model forgot the relation, snap to the nearest wall —
        # then relations (beside/on/...) align neighbors to final positions.
        self._snap_wall_huggers(placed, room, pinned)

        for _ in range(2):
            for _, obj, det in placed:
                for rel in (det.get("relations") or []):
                    try:
                        self._apply_relation(obj, rel, by_det_index, room, linked)
                        pinned.add(obj.id)
                    except Exception as e:
                        print(f"[SceneBuilder] Bad relation {rel}: {e}")

        self._resolve_overlaps(objects, room, linked, pinned)
        return objects

    WALL_HUGGERS = {
        "bed", "wardrobe", "dresser", "bookshelf", "tv_stand", "sideboard",
        "console", "desk", "sofa", "fridge", "kitchen_cabinet", "stove",
        "washing_machine", "toilet", "sink", "bathtub",
    }

    def _snap_wall_huggers(self, placed, room: RoomShell, pinned: set) -> None:
        for _, obj, det in placed:
            if obj.category not in self.WALL_HUGGERS:
                continue
            has_against = any(
                (rel.get("type") == "against")
                for rel in (det.get("relations") or [])
            )
            if has_against or obj.transform.pos[1] > 0.01:
                continue
            x, z = obj.transform.pos[0], obj.transform.pos[2]
            half_d = obj.dimensions_m[2] / 2
            # Pick the wall from where the object sits in the photo frame:
            # mid-frame furniture faces the camera -> back wall; only items
            # at the frame edges belong to the side walls.
            bbox = (det.get("bbox") or [0, 0, 0, 0])
            img_size = (obj.source or {}).get("img_size") or [1, 1]
            try:
                cx_norm = ((float(bbox[0]) + float(bbox[2])) / 2.0) / max(1.0, float(img_size[0]))
            except (TypeError, ValueError, IndexError):
                cx_norm = 0.5
            if cx_norm < 0.18:
                wall, gap = "left", (x - half_d) - (-room.width_m / 2)
            elif cx_norm > 0.82:
                wall, gap = "right", (room.width_m / 2) - (x + half_d)
            else:
                wall, gap = "back", (z - half_d) - (-room.depth_m / 2)
            # Depth estimation is noisy; for wall-hugging furniture trust the
            # prior generously (only skip when truly mid-room or already flush)
            if gap < 0 or gap > max(1.3, room.depth_m * 0.35):
                continue
            if wall == "back":
                obj.transform.pos[2] = -room.depth_m / 2 + half_d + 0.03
                obj.transform.rot_y_deg = 0.0
            elif wall == "left":
                obj.transform.pos[0] = -room.width_m / 2 + half_d + 0.03
                obj.transform.rot_y_deg = 90.0
            else:
                obj.transform.pos[0] = room.width_m / 2 - half_d - 0.03
                obj.transform.rot_y_deg = -90.0
            pinned.add(obj.id)
            print(f"[SceneBuilder] Snapped {obj.category} to {wall} wall (gap {gap:.2f}m)")

    def _apply_relation(self, obj, rel: dict, by_det_index: dict, room: RoomShell, linked: set) -> None:
        rtype = (rel.get("type") or "").lower()
        target = rel.get("target")

        if rtype == "against" and isinstance(target, str):
            depth_half = obj.dimensions_m[2] / 2 + 0.03
            if "back" in target:
                obj.transform.pos[2] = -room.depth_m / 2 + depth_half
                obj.transform.rot_y_deg = 0.0
            elif "left" in target:
                obj.transform.pos[0] = -room.width_m / 2 + depth_half
                obj.transform.rot_y_deg = 90.0
            elif "right" in target:
                obj.transform.pos[0] = room.width_m / 2 - depth_half
                obj.transform.rot_y_deg = -90.0
            return

        if rtype == "under" and isinstance(target, str):
            # Align under a back-wall feature (mirror, window, art)
            for feature in room.features:
                if feature.type == target and feature.wall == "back":
                    obj.transform.pos[0] = self._clamp(
                        feature.center_x_m,
                        -room.width_m / 2 + obj.dimensions_m[0] / 2,
                        room.width_m / 2 - obj.dimensions_m[0] / 2,
                    )
                    obj.transform.pos[2] = -room.depth_m / 2 + obj.dimensions_m[2] / 2 + 0.03
                    obj.transform.rot_y_deg = 0.0
                    return
            return

        # Remaining relations reference another object by detection index
        try:
            other = by_det_index.get(int(target))
        except (TypeError, ValueError):
            return
        if other is None or other.id == obj.id:
            return

        if rtype == "beside":
            side = 1.0 if (rel.get("side") or "right") == "right" else -1.0
            obj.transform.pos[0] = self._clamp(
                other.transform.pos[0] + side * (other.dimensions_m[0] / 2 + obj.dimensions_m[0] / 2 + 0.05),
                -room.width_m / 2 + obj.dimensions_m[0] / 2,
                room.width_m / 2 - obj.dimensions_m[0] / 2,
            )
            # Align back edges (nightstand back flush with the bed's head)
            back_edge = other.transform.pos[2] - other.dimensions_m[2] / 2
            obj.transform.pos[2] = self._clamp(
                back_edge + obj.dimensions_m[2] / 2,
                -room.depth_m / 2 + obj.dimensions_m[2] / 2,
                room.depth_m / 2 - obj.dimensions_m[2] / 2,
            )
            linked.add(frozenset((obj.id, other.id)))
        elif rtype == "on":
            obj.transform.pos[0] = other.transform.pos[0]
            obj.transform.pos[2] = other.transform.pos[2]
            obj.transform.pos[1] = round(other.transform.pos[1] + other.dimensions_m[1], 3)
            linked.add(frozenset((obj.id, other.id)))
        elif rtype == "in_front_of":
            obj.transform.pos[0] = other.transform.pos[0]
            obj.transform.pos[2] = self._clamp(
                other.transform.pos[2] + other.dimensions_m[2] / 2 + obj.dimensions_m[2] / 2 + 0.15,
                -room.depth_m / 2 + obj.dimensions_m[2] / 2,
                room.depth_m / 2 - obj.dimensions_m[2] / 2,
            )
            linked.add(frozenset((obj.id, other.id)))

    def _resolve_overlaps(
        self,
        objects: List[SceneObject],
        room: RoomShell,
        linked: Optional[set] = None,
        pinned: Optional[set] = None,
    ) -> None:
        """
        Nudge overlapping footprints apart along x. Objects placed by photo
        relations are pinned — only unpinned objects get moved, so the
        constraint-solved arrangement survives.
        """
        linked = linked or set()
        pinned = pinned or set()
        for _ in range(3):
            moved = False
            for i in range(len(objects)):
                for j in range(i + 1, len(objects)):
                    a, b = objects[i], objects[j]
                    if a.category == "rug" or b.category == "rug":
                        continue  # rugs live under other furniture
                    if frozenset((a.id, b.id)) in linked:
                        continue  # intentionally adjacent (beside/on relations)
                    if a.transform.pos[1] > 0.01 or b.transform.pos[1] > 0.01:
                        continue  # objects sitting on furniture never collide on the floor
                    if a.id in pinned and b.id in pinned:
                        continue  # both placed by the photo's relations — trust it
                    ax, az = a.transform.pos[0], a.transform.pos[2]
                    bx, bz = b.transform.pos[0], b.transform.pos[2]
                    half_w = (a.dimensions_m[0] + b.dimensions_m[0]) / 2
                    half_d = (a.dimensions_m[2] + b.dimensions_m[2]) / 2
                    dx, dz = bx - ax, bz - az
                    if abs(dx) < half_w and abs(dz) < half_d:
                        push = (half_w - abs(dx)) + 0.05
                        direction = 1.0 if dx >= 0 else -1.0
                        limit = room.width_m / 2 - 0.1
                        if a.id in pinned:
                            b.transform.pos[0] = self._clamp(bx + direction * push, -limit, limit)
                        elif b.id in pinned:
                            a.transform.pos[0] = self._clamp(ax - direction * push, -limit, limit)
                        else:
                            a.transform.pos[0] = self._clamp(ax - direction * push / 2, -limit, limit)
                            b.transform.pos[0] = self._clamp(bx + direction * push / 2, -limit, limit)
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
            "art": {"bottom_m": 1.2, "height_m": 0.7, "color": "#D8D2C4"},
            "pendant": {"bottom_m": 0.0, "height_m": 0.8, "color": "#E8E4DA"},
            "mirror": {"bottom_m": 1.0, "height_m": 0.7, "color": "#C3D3DC"},
        }
        features: List[WallFeature] = []
        for det in detected[:10]:
            ftype = (det.get("type") or "").strip().lower()
            if ftype not in defaults:
                continue
            bbox = det.get("bbox") or [0, 0, img_w, img_h]
            try:
                x0, y0, x1, y1 = [float(v) for v in bbox]
            except (TypeError, ValueError):
                continue
            cx_norm = ((x0 + x1) / 2.0) / img_w

            if ftype == "pendant":
                # Ceiling feature: x from the photo; hang it in the back
                # half of the room where pendants usually read best.
                d = defaults[ftype]
                width = self._clamp(float(det.get("width_m") or 0.35), 0.15, 1.2)
                height = self._clamp(float(det.get("height_m") or d["height_m"]),
                                     0.3, room.height_m * 0.6)
                center_x = self._clamp((cx_norm - 0.5) * room.width_m,
                                       -room.width_m / 2 + 0.3, room.width_m / 2 - 0.3)
                features.append(WallFeature(
                    id=f"pendant_{uuid.uuid4().hex[:6]}",
                    type="pendant",
                    wall="ceiling",
                    center_x_m=round(center_x, 3),
                    center_z_m=round(-room.depth_m * 0.2, 3),
                    width_m=round(width, 3),
                    height_m=round(height, 3),
                    bottom_m=0.0,
                    color=det.get("color") or d["color"],
                ))
                continue

            # Which wall? Left/right edges of the frame -> side walls,
            # otherwise the back wall (the one facing the camera).
            if cx_norm < 0.20:
                wall, wall_len = "left", room.depth_m
                center_x = 0.0
            elif cx_norm > 0.80:
                wall, wall_len = "right", room.depth_m
                center_x = 0.0
            else:
                wall, wall_len = "back", room.width_m
                center_x = (cx_norm - 0.5) * room.width_m

            d = defaults[ftype]
            style = (det.get("style") or "").strip().lower() or None
            # Models return free-form styles ("double_layer_sheer_and_heavy");
            # normalize to what the editor can render.
            if style:
                if ftype == "curtain":
                    style = "sheer" if any(k in style for k in ("sheer", "voile", "translucent")) else "solid"
                elif ftype == "window":
                    if "floor" in style or "full" in style:
                        style = "floor_to_ceiling"
                    elif "slid" in style:
                        style = "sliding_door"
                    else:
                        style = "standard"
            width = float(det.get("width_m") or ((x1 - x0) / img_w) * wall_len)
            width = self._clamp(width, 0.4, wall_len - 0.2)
            # Full-height glazing overrides the standard window defaults
            if ftype == "window" and style in ("floor_to_ceiling", "sliding_door"):
                height = room.height_m - 0.25
                bottom = 0.02
            else:
                height = self._clamp(float(det.get("height_m") or d["height_m"]), 0.4, room.height_m - 0.1)
                bottom = self._clamp(float(det.get("bottom_m") or d["bottom_m"]), 0.0, room.height_m - height)
            center_x = self._clamp(center_x, -wall_len / 2 + width / 2, wall_len / 2 - width / 2)

            features.append(WallFeature(
                id=f"{ftype}_{uuid.uuid4().hex[:6]}",
                type=ftype,
                style=style,
                wall=wall,
                center_x_m=round(center_x, 3),
                width_m=round(width, 3),
                height_m=round(height, 3),
                bottom_m=round(bottom, 3),
                color=det.get("color") or d["color"],
            ))
        return features

    @staticmethod
    def _bbox_overlap_ratio(a, b) -> float:
        """How much of bbox a is covered by bbox b (0..1)."""
        ax0, ay0, ax1, ay1 = a
        bx0, by0, bx1, by1 = b
        ix = max(0.0, min(ax1, bx1) - max(ax0, bx0))
        iy = max(0.0, min(ay1, by1) - max(ay0, by0))
        area = max(1.0, (ax1 - ax0) * (ay1 - ay0))
        return (ix * iy) / area

    def _sample_texture(self, hires_photo, det_size, bbox, kind: str,
                        obstacles=None, expected_color: Optional[str] = None):
        """
        Cut a clean wall/floor patch from the photo to use as the actual
        3D material texture — real materials instead of flat colors.
        Returns a served URL or None.
        """
        if not bbox:
            return None
        try:
            from .generation_service import generation_service

            x0, y0, x1, y1 = [float(v) for v in bbox]
            det_w, det_h = det_size

            # Hard rule: the sample must not contain any detected object or
            # feature — statistics can be fooled, geometry can't.
            for obstacle in (obstacles or []):
                try:
                    if self._bbox_overlap_ratio((x0, y0, x1, y1), [float(v) for v in obstacle]) > 0.12:
                        print(f"[SceneBuilder] {kind} sample overlaps an object — flat color instead")
                        return None
                except (TypeError, ValueError):
                    continue
            sx, sy = hires_photo.width / det_w, hires_photo.height / det_h
            crop = hires_photo.crop((
                int(max(0, x0 * sx)), int(max(0, y0 * sy)),
                int(min(hires_photo.width, x1 * sx)),
                int(min(hires_photo.height, y1 * sy)),
            ))
            if crop.width < 60 or crop.height < 60:
                return None  # too small to tile convincingly
            # Cap texture size; keep it square-ish for clean tiling
            side = min(crop.width, crop.height, 512)
            crop = crop.resize((side, side))

            # Flatten the lighting gradient (spotlights/shadows tile as
            # ugly kaleidoscope patterns) by dividing out the low-frequency
            # brightness, then reject patches that still look "busy" —
            # they contain objects/edges, and a flat color is safer.
            from PIL import ImageFilter

            arr = np.asarray(crop.convert("RGB"), dtype=np.float32)
            blurred = np.asarray(
                crop.convert("RGB").filter(ImageFilter.GaussianBlur(radius=side / 4)),
                dtype=np.float32,
            )
            mean_color = arr.mean(axis=(0, 1))
            flat = arr / np.clip(blurred, 8.0, None) * mean_color
            flat = np.clip(flat, 0, 255).astype(np.uint8)

            busyness = float(flat.std(axis=(0, 1)).mean())
            limit = 38.0 if kind == "floor" else 30.0
            if busyness > limit:
                print(f"[SceneBuilder] {kind} patch too busy (std {busyness:.0f} > {limit}) "
                      f"— using flat color instead")
                return None

            # The patch should roughly match the detected surface color;
            # a big mismatch means it sampled something else (shadow, object).
            if expected_color:
                try:
                    hex_str = expected_color.lstrip("#")
                    target = np.array([int(hex_str[i:i + 2], 16) for i in (0, 2, 4)], dtype=np.float32)
                    distance = float(np.linalg.norm(mean_color - target))
                    if distance > 110.0:
                        print(f"[SceneBuilder] {kind} patch color off by {distance:.0f} "
                              f"from detected color — flat color instead")
                        return None
                except ValueError:
                    pass

            from PIL import Image as PILImage
            return generation_service.save_texture(PILImage.fromarray(flat), kind)
        except Exception as e:
            print(f"[SceneBuilder] Could not sample {kind} texture: {e}")
            return None

    # ---------- main entry ----------

    @staticmethod
    def _capped(image, max_size: int):
        w, h = image.size
        if max(w, h) <= max_size:
            return image
        scale = max_size / max(w, h)
        from PIL import Image as PILImage
        return image.resize((int(w * scale), int(h * scale)), PILImage.Resampling.LANCZOS)

    async def build_scene_from_image(self, image_base64: str):
        original = depth_service._decode_base64_image(image_base64)

        # Detection runs at higher resolution than depth so small objects
        # (lamps, nightstands) keep enough pixels to be found and cropped.
        detection_image = self._capped(original, 1280)
        image_size = detection_image.size  # (w, h) — bbox coordinate space
        detection_base64 = depth_service._encode_image_base64(detection_image, "JPEG")

        # Depth map (best-effort; placement degrades gracefully without it).
        # Bbox->depth sampling is normalized, so different resolutions are fine.
        depth_map = None
        try:
            depth_map, _ = depth_service.generate_depth_map_v2(image_base64)
        except Exception as e:
            print(f"[SceneBuilder] Depth estimation unavailable, using layout-only placement: {e}")

        detection = await self.detect_room(detection_base64, image_size)
        # Understanding layer: second pass reviews the analysis against the photo
        detection = await self.refine_detection(detection_base64, image_size, detection)

        hires = self._capped(original, 2048)

        # Anything detected is an obstacle for material sampling: a texture
        # patch containing furniture/curtains tiles as garbage.
        obstacles = [o.get("bbox") for o in (detection.get("objects") or []) if o.get("bbox")]
        obstacles += [f.get("bbox") for f in (detection.get("features") or []) if f.get("bbox")]

        est = detection.get("room_estimate") or {}
        room = RoomShell(
            width_m=self._clamp(float(est.get("width_m") or 4.0), 2.0, 10.0),
            depth_m=self._clamp(float(est.get("depth_m") or 3.5), 2.0, 10.0),
            height_m=self._clamp(float(est.get("height_m") or 2.6), 2.2, 4.0),
            wall_material=MaterialDef(
                color=detection.get("wall_color") or "#F2EDE4",
                texture_url=self._sample_texture(
                    hires, image_size, detection.get("wall_sample_bbox"), "wall",
                    obstacles=obstacles, expected_color=detection.get("wall_color"),
                ),
            ),
            floor_material=MaterialDef(
                color=detection.get("floor_color") or "#A98B6D",
                texture=detection.get("floor_type"),
                texture_url=self._sample_texture(
                    hires, image_size, detection.get("floor_sample_bbox"), "floor",
                    obstacles=obstacles, expected_color=detection.get("floor_color"),
                ),
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
        # Return a high-res copy of the photo for persistence — "Make
        # realistic" crops per-object images from it, so resolution matters.
        return data, self._capped(original, 2048)


scene_builder = SceneBuilder()
