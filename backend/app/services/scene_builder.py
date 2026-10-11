"""
ReimagineAI - Scene Builder

Turns a single room photo into a structured, editable 3D scene that lines
up with the photo:

1. The vision model (OpenAI / Gemini) reads the photo: furniture with boxes,
   which way each piece faces, wall features, materials, relations.
2. MoGe-2 metric depth + room_geometry *measure* the room: the camera pose,
   floor/walls/ceiling, and each object's real position, size and heading.
3. Every object gets a catalog asset (shape picked from its label), sized to
   its measurement; windows/doors land on the wall their rays hit; colors
   and the floor texture come from the photo's own pixels.
4. The photo's camera is stored with the scene, so the editor opens at the
   exact photo viewpoint and can project the photo onto the room shell.

If the geometry can't be recovered (no floor visible, model unavailable),
placement falls back to the vision model's own floor-plan estimate.
"""
from __future__ import annotations

import asyncio
import copy
import json
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ..config import get_settings
from ..models.scene import (
    AssetRef,
    MaterialDef,
    PhotoProjection,
    RoomShell,
    SceneCamera,
    SceneData,
    SceneObject,
    Transform,
    WallFeature,
)
from . import room_geometry
from .catalog_service import catalog_service
from .depth_service import depth_service
from .gemini_service import gemini_service
from .openai_service import openai_service
from .semantic_service import semantic_service

settings = get_settings()

# How each provider reports boxes. Gemini is trained on box_2d
# [y_min, x_min, y_max, x_max] normalized to 0-1000 — asking for anything
# else costs accuracy; OpenAI gets pixel boxes with the image size.
BOX_FORMATS = {
    "gemini": {
        "key": "box_2d",
        "order": "[y_min, x_min, y_max, x_max]",
        "rule": "box_2d values are normalized to 0-1000 (0 = top/left edge of the image, "
                "1000 = bottom/right edge), in the order [y_min, x_min, y_max, x_max]. "
                "Boxes must tightly enclose the whole visible object.",
    },
    "openai": {
        "key": "bbox",
        "order": "[x_min, y_min, x_max, y_max]",
        "rule": "bbox is in pixel coordinates of THIS image (integers), in the order "
                "[x_min, y_min, x_max, y_max]. Boxes must tightly enclose the whole visible object.",
    },
}

DETECTION_PROMPT = """You are an interior-design vision system. Analyze this room photo.

Return ONLY valid JSON (no markdown fences) with this exact structure:
{
  "room_type": "living room",
  "style": "modern",
  "room_estimate": {"width_m": 4.0, "depth_m": 3.5, "height_m": 2.6},
  "wall_color": "#EDE8DF",
  "floor_color": "#A98B6D",
  "floor_type": "wood",
  "wall_sample_<<BOX>>": <<ORDER>>,
  "floor_sample_<<BOX>>": <<ORDER>>,
  "objects": [
    {
      "label": "grey fabric sofa",
      "category": "sofa",
      "<<BOX>>": <<ORDER>>,
      "color": "#8A8A8A",
      "width_m": 2.0,
      "against_wall": true,
      "facing": "camera",
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
    {"type": "window", "style": "floor_to_ceiling", "<<BOX>>": <<ORDER>>, "color": "#FFFFFF", "width_m": 1.5},
    {"type": "curtain", "style": "sheer", "<<BOX>>": <<ORDER>>, "color": "#8A8A8A", "width_m": 1.5},
    {"type": "door", "<<BOX>>": <<ORDER>>, "color": "#F0F0F0", "width_m": 0.9},
    {"type": "art", "<<BOX>>": <<ORDER>>, "color": "#D8D2C4", "width_m": 0.5},
    {"type": "pendant", "<<BOX>>": <<ORDER>>, "color": "#E8E4DA", "width_m": 0.35},
    {"type": "mirror", "<<BOX>>": <<ORDER>>, "color": "#C3D3DC", "width_m": 0.6}
  ]
}

Rules:
- <<BOX_RULE>>
- category must be a simple generic furniture type: sofa, armchair, chair, table,
  coffee_table, side_table, desk, bed, nightstand, wardrobe, dresser, bookshelf, tv, tv_stand,
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
- facing: which way the object's FRONT points in the photo, from the viewer's
  point of view: "camera" (toward the viewer), "away", "left" or "right".
  The front of a sofa/chair is where you sit, of a bed the foot end, of a
  wardrobe/dresser/nightstand the doors or drawers, of a TV the screen.
  Items without a clear front (round tables, plants, rugs, lamps): "camera".
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
- wall_sample_<<BOX>>: a rectangular patch showing ONLY bare wall (no furniture,
  no art, no windows, no strong shadows) — used to sample the wall material.
- floor_sample_<<BOX>>: a rectangular patch showing ONLY bare floor — used to
  sample the floor material. Pick the cleanest, most evenly lit areas.
- features: windows, doors, curtains, framed wall art / picture groups
  ("art"), hanging ceiling lights ("pendant"), and WALL-MOUNTED mirrors
  ("mirror") go in "features" with their boxes and dominant colors.
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
        self._depth_slot = asyncio.Semaphore(1)  # one geometry inference at a time

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

    async def _ask_json(
        self, prompts: Dict[str, str], image_base64: str, prefer: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Run a vision->JSON query on the configured provider, falling back
        to the other one. The provider order comes from settings
        (scene_analysis_provider: "openai" | "gemini") unless `prefer`
        overrides it; each provider gets its own prompt (box formats differ).
        """
        first = prefer or settings.scene_analysis_provider.lower()
        order = ["openai", "gemini"] if first == "openai" else ["gemini", "openai"]
        last_error: Optional[Exception] = None
        for provider in order:
            try:
                if provider == "openai":
                    if not settings.openai_api_key:
                        continue
                    return await self._openai_json(prompts["openai"], image_base64)
                # The Gemini SDK call is synchronous: keep it off the event loop
                result = await asyncio.to_thread(self._gemini_json, prompts["gemini"], image_base64)
                if result is not None:
                    return result
            except Exception as e:
                last_error = e
                print(f"[SceneBuilder] {provider} analysis failed, trying next provider: {e}")
        raise RuntimeError(f"Room analysis failed on all providers: {last_error}")

    @staticmethod
    def _fill_prompt(template: str, provider: str, image_size: Tuple[int, int]) -> str:
        fmt = BOX_FORMATS[provider]
        text = (template.replace("<<BOX_RULE>>", fmt["rule"])
                .replace("<<BOX>>", fmt["key"]).replace("<<ORDER>>", fmt["order"]))
        if provider == "openai":
            text += f"\nThe image is {image_size[0]}x{image_size[1]} pixels."
        return text

    async def detect_room(self, image_base64: str, image_size: Tuple[int, int]) -> Dict[str, Any]:
        """Run furniture/room detection on the configured vision provider."""
        prompts = {p: self._fill_prompt(DETECTION_PROMPT, p, image_size) for p in BOX_FORMATS}
        return self._canonicalize(await self._ask_json(prompts, image_base64), image_size)

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
        template = """You are reviewing a room analysis for a 3D reconstruction.

Here is the photo and a first-pass analysis of it:

<<ANALYSIS>>

Carefully compare the analysis against the photo and return the CORRECTED
full JSON in the exact same schema. Check specifically:
1. MISSED furniture: nightstands, lamps, plants, stools, side tables —
   anything on the floor that is not yet in "objects". Add them with boxes.
2. Boxes: every box must tightly enclose its whole object. <<BOX_RULE>>
3. facing: is each object's front direction right ("camera", "away",
   "left", "right" from the viewer's point of view)?
4. Window style: is it really "standard", or is it floor_to_ceiling glazing
   or a sliding door? Are curtains sheer or solid? Fix "style" fields.
5. Wrong entries: remove objects that are actually part of another object
   (pillows on a bed) or that do not exist in the photo.
6. Sizes: fix clearly wrong width_m estimates (a bed is ~1.4-2.0m wide,
   a nightstand ~0.4-0.6m).
7. room_estimate, wall/floor colors and sample boxes: adjust if wrong.
8. plan_pos: mentally draw the top-down floor plan and verify each object's
   x_m/z_m matches where it stands in the photo (origin = room center,
   back wall at z=-depth/2). Fix any object that would end up on the wrong
   side of the room or overlapping another object's footprint.

Return ONLY the corrected JSON, same schema, no commentary."""

        prompts = {}
        for provider in BOX_FORMATS:
            analysis = json.dumps(self._render_boxes(first_pass, provider, image_size), indent=1)
            prompts[provider] = self._fill_prompt(template.replace("<<ANALYSIS>>", analysis), provider, image_size)
        try:
            # Gemini is trained for box grounding: when it is available it does
            # the review pass, so every box gets its precise native box_2d.
            refined = await self._ask_json(
                prompts, image_base64, prefer="gemini" if gemini_service.client else None
            )
            # Sanity: a valid refinement must keep the core keys
            if isinstance(refined, dict) and "objects" in refined:
                refined = self._canonicalize(refined, image_size)
                n_before = len(first_pass.get("objects") or [])
                n_after = len(refined.get("objects") or [])
                print(f"[SceneBuilder] Refinement pass: {n_before} -> {n_after} objects")
                return refined
        except Exception as e:
            print(f"[SceneBuilder] Refinement pass failed (using first pass): {e}")
        return first_pass

    # ---------- box formats ----------

    @staticmethod
    def _px_box(item: Dict[str, Any], key_2d: str, key_px: str, size: Tuple[int, int]) -> Optional[List[float]]:
        """Pixel [x0, y0, x1, y1] from a Gemini box_2d or an OpenAI pixel bbox."""
        w, h = size
        try:
            if item.get(key_2d) is not None:
                y0, x0, y1, x1 = [float(v) for v in item[key_2d]]
                box = [x0 / 1000.0 * w, y0 / 1000.0 * h, x1 / 1000.0 * w, y1 / 1000.0 * h]
            elif item.get(key_px) is not None:
                box = [float(v) for v in item[key_px]]
            else:
                return None
        except (TypeError, ValueError):
            return None
        x0, x1 = sorted((min(max(box[0], 0.0), w), min(max(box[2], 0.0), w)))
        y0, y1 = sorted((min(max(box[1], 0.0), h), min(max(box[3], 0.0), h)))
        if x1 - x0 < 2 or y1 - y0 < 2:
            return None
        return [x0, y0, x1, y1]

    @staticmethod
    def _text(value: Any) -> Optional[str]:
        """Model output field as a trimmed string (models sometimes return numbers/objects)."""
        if value is None or isinstance(value, (dict, list)):
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _hex(value: Any) -> Optional[str]:
        text = str(value).strip() if isinstance(value, (str, int)) else ""
        return text.upper() if re.fullmatch(r"#[0-9a-fA-F]{6}", text) else None

    def _canonicalize(self, detection: Dict[str, Any], size: Tuple[int, int]) -> Dict[str, Any]:
        """
        Normalize every box to pixel `bbox` (detection-image coordinates, used
        by the legacy layout and the enhance crops) plus a normalized `box`
        [0..1] used by the geometry, and coerce model-output fields to the
        types the pipeline expects. Objects without a usable box stay in the
        list flagged `_skip` — relations refer to objects by index.
        """
        if not isinstance(detection, dict):
            return {"objects": [], "features": []}
        w, h = size
        for key in ("room_type", "style", "floor_type"):
            detection[key] = self._text(detection.get(key))
        for key in ("wall_color", "floor_color"):
            detection[key] = self._hex(detection.get(key))
        objects = []
        for item in detection.get("objects") or []:
            item = item if isinstance(item, dict) else {}
            for key in ("label", "category", "facing"):
                item[key] = self._text(item.get(key))
            item["color"] = self._hex(item.get("color"))
            if not isinstance(item.get("relations"), list):
                item["relations"] = []
            px = self._px_box(item, "box_2d", "bbox", size)
            item.pop("box_2d", None)
            if px is None:
                item.pop("bbox", None)
                item.pop("box", None)
                item["_skip"] = True
            else:
                item["bbox"] = [int(round(v)) for v in px]
                item["box"] = [px[0] / w, px[1] / h, px[2] / w, px[3] / h]
            objects.append(item)
        detection["objects"] = objects
        features = []
        for item in detection.get("features") or []:
            if not isinstance(item, dict):
                continue
            px = self._px_box(item, "box_2d", "bbox", size)
            if px is None:
                continue  # nothing refers to features by index
            for key in ("type", "style"):
                item[key] = self._text(item.get(key))
            item["color"] = self._hex(item.get("color"))
            item.pop("box_2d", None)
            item["bbox"] = [int(round(v)) for v in px]
            item["box"] = [px[0] / w, px[1] / h, px[2] / w, px[3] / h]
            features.append(item)
        detection["features"] = features
        for surface in ("wall", "floor"):
            px = self._px_box(detection, f"{surface}_sample_box_2d", f"{surface}_sample_bbox", size)
            detection.pop(f"{surface}_sample_box_2d", None)
            detection[f"{surface}_sample_bbox"] = [int(round(v)) for v in px] if px else None
        return detection

    @staticmethod
    def _render_boxes(detection: Dict[str, Any], provider: str, size: Tuple[int, int]) -> Dict[str, Any]:
        """Re-express canonical boxes in a provider's native format (refinement prompt)."""
        w, h = size
        out = copy.deepcopy(detection)

        def as_2d(px):
            x0, y0, x1, y1 = px
            return [round(y0 / h * 1000), round(x0 / w * 1000), round(y1 / h * 1000), round(x1 / w * 1000)]

        for group in ("objects", "features"):
            for item in out.get(group) or []:
                for internal in ("box", "_skip", "_entry_id"):
                    item.pop(internal, None)
                if provider == "gemini" and item.get("bbox"):
                    item["box_2d"] = as_2d(item.pop("bbox"))
        for surface in ("wall", "floor"):
            px = out.get(f"{surface}_sample_bbox")
            if provider == "gemini":
                out.pop(f"{surface}_sample_bbox", None)
                if px:
                    out[f"{surface}_sample_box_2d"] = as_2d(px)
        return out

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
            if det.get("_skip"):
                continue  # judged not to be modelable furniture
            bbox = det.get("bbox") or [0, 0, img_w, img_h]
            try:
                x0, y0, x1, y1 = [float(v) for v in bbox]
            except (TypeError, ValueError):
                x0, y0, x1, y1 = 0.0, 0.0, float(img_w), float(img_h)
            x0, x1 = sorted((self._clamp(x0, 0, img_w), self._clamp(x1, 0, img_w)))
            y0, y1 = sorted((self._clamp(y0, 0, img_h), self._clamp(y1, 0, img_h)))
            if x1 - x0 < 4 or y1 - y0 < 4:
                continue

            entry = self._entry_for(det)
            category = entry["category"] if entry else catalog_service.normalize_category(det.get("category", ""))
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
            # prior generously. Beds/wardrobes etc. are essentially NEVER
            # free-standing — snap them regardless of the estimated gap.
            always_snap = obj.category in ("bed", "wardrobe", "fridge", "bathtub", "toilet")
            if gap < 0 or (not always_snap and gap > max(1.3, room.depth_m * 0.35)):
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
            # Only small objects sit on furniture (lamp on nightstand, TV on
            # stand) — a wardrobe can't be "on" another wardrobe, and nothing
            # stacks above head height.
            if obj.dimensions_m[0] > 0.9 or obj.dimensions_m[1] > 1.0:
                return
            top_y = other.transform.pos[1] + other.dimensions_m[1]
            if top_y + obj.dimensions_m[1] > room.height_m - 0.2:
                return
            obj.transform.pos[0] = other.transform.pos[0]
            obj.transform.pos[2] = other.transform.pos[2]
            obj.transform.pos[1] = round(top_y, 3)
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

            # Flatten the lighting gradient, then reject patches that still
            # look "busy" — they contain objects/edges, and a flat color is safer.
            flat_img = self._flatten_lighting(crop)
            flat = np.asarray(flat_img, dtype=np.uint8)
            mean_color = np.asarray(crop.convert("RGB"), dtype=np.float32).mean(axis=(0, 1))

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

            return generation_service.save_texture(flat_img, kind)
        except Exception as e:
            print(f"[SceneBuilder] Could not sample {kind} texture: {e}")
            return None

    @staticmethod
    def _flatten_lighting(image):
        """
        Divide out the low-frequency brightness of a texture patch:
        spotlights/shadows would otherwise tile as kaleidoscope patterns.
        """
        from PIL import Image as PILImage
        from PIL import ImageFilter

        rgb = image.convert("RGB")
        arr = np.asarray(rgb, dtype=np.float32)
        blurred = np.asarray(
            rgb.filter(ImageFilter.GaussianBlur(radius=min(rgb.size) / 4)), dtype=np.float32
        )
        mean_color = arr.mean(axis=(0, 1))
        flat = arr / np.clip(blurred, 8.0, None) * mean_color
        return PILImage.fromarray(np.clip(flat, 0, 255).astype(np.uint8))

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
        original, exif_hfov = depth_service.decode_photo(image_base64)

        # Detection runs at higher resolution than depth so small objects
        # (lamps, nightstands) keep enough pixels to be found and cropped.
        detection_image = self._capped(original, 1280)
        image_size = detection_image.size  # (w, h) — bbox coordinate space
        detection_base64 = depth_service._encode_image_base64(detection_image, "JPEG")

        # Geometry (CPU) runs on a worker thread while the vision model reads
        # the photo. Requests queue for it here, in the event loop, instead of
        # parking in the shared thread pool (Gemini calls use it too). The
        # model estimates the FOV on its own so EXIF can be cross-checked.
        async def measure_depth():
            async with self._depth_slot:
                return await asyncio.to_thread(depth_service.metric_depth, original)

        depth_task = asyncio.create_task(measure_depth())

        try:
            detection = await self.detect_room(detection_base64, image_size)
            # Understanding layer: second pass reviews the analysis against the photo
            detection = await self.refine_detection(detection_base64, image_size, detection)
            # Which catalog shape represents each item (L-shaped sofa, round table...)
            await self._match_catalog(detection)
        except BaseException:
            depth_task.cancel()  # the worker thread finishes on its own; drop its result
            raise

        depth, model_hfov, depth_model = None, None, None
        try:
            depth, model_hfov, depth_model = await depth_task
        except Exception as e:
            print(f"[SceneBuilder] Depth estimation unavailable, using layout-only placement: {e}")

        # Return a high-res copy of the photo for persistence — "Make
        # realistic" crops per-object images from it, so resolution matters.
        hires = self._capped(original, 2048)

        geometry = None
        if depth is not None:
            try:
                geometry = await asyncio.to_thread(
                    self._analyze, depth, detection, image_size, exif_hfov, model_hfov, depth_model
                )
            except Exception as e:
                import traceback

                traceback.print_exc()
                print(f"[SceneBuilder] Geometry analysis failed, using layout-only placement: {e}")

        data = None
        if geometry is not None:
            try:
                data = await asyncio.to_thread(
                    self._measured_scene, detection, geometry, image_size, hires, depth_model
                )
            except Exception as e:
                import traceback

                traceback.print_exc()
                print(f"[SceneBuilder] Measured reconstruction failed, using layout-only placement: {e}")
        if data is None:
            closeness = None
            if depth is not None:
                # Legacy layout expects disparity-like closeness (higher = nearer)
                inv = np.where(depth > 0, 1.0 / np.maximum(depth, 1e-3), 0.0)
                closeness = (inv - inv.min()) / max(1e-6, float(inv.max() - inv.min()))
            data = self._layout_scene(detection, closeness, image_size, hires)
        return data, hires

    # ---------- measured reconstruction ----------

    def _analyze(self, depth, detection, image_size, exif_hfov, model_hfov, depth_model):
        """Camera + room box from depth, ignoring regions with fake depth."""
        # Glass shows the outside, mirrors a reflected room, open doors the
        # next room: none of it belongs to this room's walls.
        unreliable = [f["box"] for f in detection.get("features") or []
                      if (f.get("type") or "").lower() in ("window", "mirror", "door")]
        unreliable += [o["box"] for o in detection.get("objects") or []
                       if o.get("box") and catalog_service.normalize_category(o.get("category") or "") == "mirror"]
        floor_hint = None
        fb = detection.get("floor_sample_bbox")
        if fb:
            w, h = image_size
            floor_hint = [fb[0] / w, fb[1] / h, fb[2] / w, fb[3] / h]
        def plausible(v):
            return v is not None and 20.0 <= v <= 130.0  # NaN fails too

        exif_hfov = exif_hfov if plausible(exif_hfov) else None
        model_hfov = model_hfov if plausible(model_hfov) else None
        # EXIF describes the full sensor: a cropped photo keeps the 35mm focal
        # but shows a narrower view. Trust it only when the model agrees.
        use_exif = exif_hfov is not None and (
            model_hfov is None or abs(exif_hfov - model_hfov) <= 0.15 * model_hfov
        )
        if exif_hfov is not None and not use_exif:
            print(f"[SceneBuilder] EXIF FOV {exif_hfov:.0f} disagrees with the model's "
                  f"{model_hfov:.0f} (cropped photo?) — using the model")
        fov = exif_hfov if use_exif else model_hfov
        return room_geometry.analyze_room(
            depth,
            image_size,
            fov_hint=fov,
            fov_source="exif" if use_exif else (depth_model or "model"),
            exclude_boxes=unreliable,
            floor_hint_box=floor_hint,
            estimate=detection.get("room_estimate") or {},
        )

    # Typical heights (m) with how standardized they are (cue weight). Only
    # counters, tables and appliances are truly standard; designer
    # nightstands and sofas vary a lot, so they barely count.
    STANDARD_HEIGHTS = {
        "table": (0.75, 1.0), "desk": (0.75, 1.0), "kitchen_cabinet": (0.9, 1.0),
        "kitchen_island": (0.9, 1.0), "stove": (0.9, 0.8), "washing_machine": (0.85, 0.8),
        "sink": (0.85, 0.5), "nightstand": (0.55, 0.2), "sofa": (0.85, 0.2),
        "armchair": (0.85, 0.2), "chair": (0.88, 0.3), "fridge": (1.8, 0.5),
        "toilet": (0.75, 0.4), "coffee_table": (0.45, 0.2), "side_table": (0.55, 0.2),
        "dresser": (0.85, 0.2), "wardrobe": (2.0, 0.2), "console": (0.8, 0.2),
        "sideboard": (0.8, 0.2), "bench": (0.45, 0.2), "bathtub": (0.55, 0.3),
    }
    # Things that can stand on other furniture; everything else is on the floor
    STACKABLE = {"lamp_table", "plant", "tv", "mirror"}

    def _measured_scene(self, detection, geom, image_size, hires, depth_model) -> SceneData:
        # Keyed by the original index: relations ("on": 2) refer to it
        dets = {i: d for i, d in enumerate((detection.get("objects") or [])[:20]) if not d.get("_skip")}

        # Nearest first (lower bottom edge = closer): each object claims only
        # its own depth-edge-bounded blob, so a bed in front of a nightstand
        # can't hand the nightstand its duvet, nor swallow a console behind it.
        order = sorted(dets, key=lambda i: -dets[i]["box"][3])
        occupied = np.zeros(geom.valid.shape, bool)
        placed: Dict[int, tuple] = {}
        for i in order:
            det = dets[i]
            entry = self._entry_for(det)
            if entry is None:
                print(f"[SceneBuilder] Skipping unmatched detection: {det.get('label')} ({det.get('category')})")
                continue
            category = entry["category"]
            est = room_geometry.place_object(
                geom, det["box"], self._prior_dims(entry, det),
                facing=det.get("facing"),
                wall_hugger=category in self.WALL_HUGGERS,
                flat=category == "rug",
                occupied=occupied,
                stackable=category in self.STACKABLE,
            )
            if est is None:
                print(f"[SceneBuilder] Could not place {det.get('label')}: no usable depth or floor contact")
                continue
            if est.mask is not None and category != "rug":
                occupied |= est.mask
            placed[i] = (det, entry, est)

        # Metric-scale correction from things of standard size
        s = self._scale_from_cues(placed, detection, geom)
        if s:
            print(f"[SceneBuilder] Metric scale correction x{s:.3f}")
            room_geometry.rescale(geom, s)
            placed = {i: (d, e, est.scaled(s)) for i, (d, e, est) in placed.items()}

        objects = self._objects_from_estimates(placed, geom, hires, image_size)
        room = self._measured_shell(detection, geom, image_size, hires, placed)
        room.features = self._measured_features(detection, geom)

        return SceneData(
            room_type=detection.get("room_type") or "room",
            style=detection.get("style"),
            room=room,
            objects=objects,
            camera=SceneCamera(**geom.editor_camera()),
            projection=self._projection(geom, hires),
            geometry={"source": "measured", "model": depth_model, **geom.quality},
        )

    def _entry_for(self, det: Dict[str, Any]) -> Optional[dict]:
        if det.get("_entry_id"):
            entry = catalog_service.get_entry(det["_entry_id"])
            if entry:
                return entry
        return catalog_service.match_label(det.get("label") or "", det.get("category") or "", det.get("width_m"))

    def _prior_dims(self, entry: dict, det: Dict[str, Any]) -> List[float]:
        """Expected size: catalog proportions scaled to the model's width estimate."""
        dims = [float(v) for v in entry["dims_m"]]
        try:
            width = float(det.get("width_m") or 0)
        except (TypeError, ValueError):
            width = 0.0
        if width > 0:
            ratio = self._clamp(width / dims[0], 0.6, 1.6)
            dims = [dims[0] * ratio, dims[1], dims[2] * ratio]
        return dims

    def _scale_from_cues(self, placed, detection, geom) -> Optional[float]:
        cues = []
        cam = geom.t
        for det, entry, est in placed.values():
            if est.method != "depth" or est.confidence < 0.5:
                continue
            std = self.STANDARD_HEIGHTS.get(entry["category"])
            if std and est.visible_height:
                cues.append((std[0], est.visible_height, std[1]))
            # Widths only for pieces seen face-on (side-on widths are foreshortened)
            try:
                est_w = float(det.get("width_m") or 0)
            except (TypeError, ValueError):
                est_w = 0.0
            if est_w and est.visible_width:
                yaw = np.radians(est.rot_y_deg)
                front = np.array([np.sin(yaw), np.cos(yaw)])
                to_cam = np.array([cam[0] - est.center[0], cam[2] - est.center[2]])
                if front @ to_cam > 0.7 * np.linalg.norm(to_cam):
                    cues.append((est_w, est.visible_width, 0.2))
        for det in detection.get("features") or []:
            if (det.get("type") or "").lower() != "door":
                continue
            box = det["box"]
            if box[1] < 0.02 or box[3] > 0.98:
                continue  # top or bottom cut off
            f = room_geometry.place_feature(geom, box, "door")
            if f and f.bottom < 0.15:
                cues.append((2.03, f.height, 1.2))
        if geom.box.observed.get("ceiling"):
            cues.append((2.6, geom.box.height, 1.0))
        s = room_geometry.semantic_scale(cues)
        if s is None or abs(s - 1.0) < 0.04:
            return None
        return float(np.clip(s, 0.85, 1.18))

    @staticmethod
    def _footprint_half(obj: SceneObject) -> Tuple[float, float]:
        w, _, d = obj.dimensions_m
        quarter = round((obj.transform.rot_y_deg % 180.0) / 90.0) % 2 == 1
        return (d / 2.0, w / 2.0) if quarter else (w / 2.0, d / 2.0)

    def _objects_from_estimates(self, placed, geom, hires, image_size) -> List[SceneObject]:
        by_index: Dict[int, SceneObject] = {}
        confidence: Dict[str, float] = {}
        for i, (det, entry, est) in placed.items():
            color = self._pixels_color(hires, est.mask) if entry["category"] != "rug" else None
            if not color:
                color = det.get("color") if isinstance(det.get("color"), str) else None
            obj = SceneObject(
                id=f"{entry['category']}_{uuid.uuid4().hex[:6]}",
                category=entry["category"],
                label=det.get("label") or entry["name"],
                asset=AssetRef(type="catalog", ref=entry["id"]),
                transform=Transform(
                    pos=[round(est.center[0], 3), round(est.center[1], 3), round(est.center[2], 3)],
                    rot_y_deg=est.rot_y_deg,
                ),
                dimensions_m=[round(float(v), 3) for v in est.dims],
                material_override=MaterialDef(color=color) if color else None,
                source={
                    "detected_from": "photo",
                    "bbox": det["bbox"],
                    "img_size": list(image_size),  # bbox coordinate space
                    "box": [round(v, 4) for v in det["box"]],
                    "raw_category": det.get("category"),
                    "facing": det.get("facing"),
                    "method": est.method,
                    "confidence": est.confidence,
                },
            )
            by_index[i] = obj
            confidence[obj.id] = est.confidence

        # Stack small things on their support ("lamp ON nightstand")
        for i, (det, entry, est) in placed.items():
            obj = by_index[i]
            support = None
            for rel in det.get("relations") or []:
                if isinstance(rel, dict) and (rel.get("type") or "").lower() == "on":
                    try:
                        support = by_index.get(int(rel.get("target")))
                    except (TypeError, ValueError):
                        support = None
            explicit = support is not None
            if support is None and obj.transform.pos[1] > 0.15:
                support = self._support_below(obj, by_index.values())
            if support is None or support.id == obj.id:
                continue
            if explicit and est.method != "depth" and obj.dimensions_m[1] > 0.7:
                # Unmeasured prior (e.g. a floor-lamp size for a bedside lamp)
                obj.dimensions_m[1] = 0.55
            if obj.dimensions_m[1] > 1.2:
                continue
            top = support.transform.pos[1] + support.dimensions_m[1]
            if top + obj.dimensions_m[1] > geom.box.height - 0.1:
                continue
            obj.transform.pos[1] = round(top, 3)
            hx, hz = self._footprint_half(support)
            ox, oz = self._footprint_half(obj)
            sx, sz = support.transform.pos[0], support.transform.pos[2]
            obj.transform.pos[0] = round(self._clamp(obj.transform.pos[0], sx - max(0.0, hx - ox), sx + max(0.0, hx - ox)), 3)
            obj.transform.pos[2] = round(self._clamp(obj.transform.pos[2], sz - max(0.0, hz - oz), sz + max(0.0, hz - oz)), 3)

        objects = list(by_index.values())
        self._separate(objects, geom.box, confidence)
        return objects

    def _support_below(self, obj: SceneObject, others) -> Optional[SceneObject]:
        """The object whose top surface this one rests on, if any."""
        ox, oz = obj.transform.pos[0], obj.transform.pos[2]
        best = None
        for other in others:
            if other.id == obj.id or other.transform.pos[1] > 0.05:
                continue
            hx, hz = self._footprint_half(other)
            if abs(ox - other.transform.pos[0]) > hx or abs(oz - other.transform.pos[2]) > hz:
                continue
            top = other.transform.pos[1] + other.dimensions_m[1]
            gap = abs(obj.transform.pos[1] - top)
            if gap < 0.25 and (best is None or gap < best[0]):
                best = (gap, other)
        return best[1] if best else None

    def _separate(self, objects: List[SceneObject], box, confidence: Dict[str, float]) -> None:
        """
        Resolve footprint overlaps left by measurement noise: the less
        certain object yields, along the axis of least penetration.
        """
        floor_objs = [o for o in objects if o.category != "rug" and o.transform.pos[1] < 0.05]
        for _ in range(4):
            moved = False
            for a_i in range(len(floor_objs)):
                for b_i in range(a_i + 1, len(floor_objs)):
                    a, b = floor_objs[a_i], floor_objs[b_i]
                    ahx, ahz = self._footprint_half(a)
                    bhx, bhz = self._footprint_half(b)
                    dx = b.transform.pos[0] - a.transform.pos[0]
                    dz = b.transform.pos[2] - a.transform.pos[2]
                    px = ahx + bhx - abs(dx)
                    pz = ahz + bhz - abs(dz)
                    if px <= 0.01 or pz <= 0.01:
                        continue
                    mover, anchor = (a, b) if confidence.get(a.id, 0) < confidence.get(b.id, 0) else (b, a)
                    sign = 1.0 if mover is b else -1.0
                    mhx, mhz = self._footprint_half(mover)
                    if px < pz:
                        step = (px + 0.02) * (1.0 if dx >= 0 else -1.0) * sign
                        mover.transform.pos[0] = round(self._clamp(
                            mover.transform.pos[0] + step, box.x_min + mhx, box.x_max - mhx), 3)
                    else:
                        step = (pz + 0.02) * (1.0 if dz >= 0 else -1.0) * sign
                        mover.transform.pos[2] = round(self._clamp(
                            mover.transform.pos[2] + step, box.z_min + mhz, box.z_max - mhz), 3)
                    moved = True
            if not moved:
                break

    @staticmethod
    def _pixels_color(hires, mask) -> Optional[str]:
        """Representative color of masked photo pixels (lit side, not shadows)."""
        if mask is None or mask.sum() < 20:
            return None
        import cv2

        m = cv2.resize(mask.astype(np.uint8), hires.size, interpolation=cv2.INTER_NEAREST).astype(bool)
        px = np.asarray(hires.convert("RGB"))[m].astype(np.float32)
        if len(px) < 50:
            return None
        if len(px) > 40000:
            px = px[np.random.default_rng(0).choice(len(px), 40000, replace=False)]
        lum = px @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
        lo, hi = np.percentile(lum, [50, 92])
        sel = px[(lum >= lo) & (lum <= hi)]
        if len(sel) < 10:
            sel = px
        r, g, b = np.median(sel, axis=0)
        return "#{:02X}{:02X}{:02X}".format(int(r), int(g), int(b))

    def _structure_color(self, hires, geom, label: int) -> Optional[str]:
        return self._pixels_color(hires, geom.structure == label)

    def _measured_shell(self, detection, geom, image_size, hires, placed) -> RoomShell:
        from .generation_service import generation_service

        b = geom.box
        obstacles = [o.get("bbox") for o in (detection.get("objects") or []) if o.get("bbox")]
        obstacles += [f.get("bbox") for f in (detection.get("features") or []) if f.get("bbox")]

        # Top-down floor patch at its true metric size
        blocked = np.zeros(geom.valid.shape, bool)
        for _, _, est in placed.values():
            if est.mask is not None:
                blocked |= est.mask
        floor_url, tile_m = None, None
        try:
            patch, tile_m = room_geometry.rectified_floor_patch(hires, geom, blocked)
            if patch is not None:
                floor_url = generation_service.save_texture(self._flatten_lighting(patch), "floor")
        except Exception as e:
            print(f"[SceneBuilder] Floor rectification failed: {e}")
        if floor_url is None:
            tile_m = None
            floor_url = self._sample_texture(
                hires, image_size, detection.get("floor_sample_bbox"), "floor",
                obstacles=obstacles, expected_color=detection.get("floor_color"),
            )

        wall_color = self._structure_color(hires, geom, room_geometry.WALL) or detection.get("wall_color") or "#F2EDE4"
        floor_color = self._structure_color(hires, geom, room_geometry.FLOOR) or detection.get("floor_color") or "#A98B6D"
        ceiling_color = self._structure_color(hires, geom, room_geometry.CEILING) or "#FFFFFF"
        return RoomShell(
            width_m=round(b.width, 3),
            depth_m=round(b.depth, 3),
            height_m=round(b.height, 3),
            wall_material=MaterialDef(
                color=wall_color,
                texture_url=self._sample_texture(
                    hires, image_size, detection.get("wall_sample_bbox"), "wall",
                    obstacles=obstacles, expected_color=wall_color,
                ),
            ),
            floor_material=MaterialDef(
                color=floor_color,
                texture=detection.get("floor_type"),
                texture_url=floor_url,
                texture_scale_m=round(tile_m, 3) if tile_m else None,
            ),
            ceiling_material=MaterialDef(color=ceiling_color),
        )

    FEATURE_DEFAULTS = {
        "window": "#EAF2F8", "door": "#EFEBE2", "curtain": "#B9B2A6",
        "art": "#D8D2C4", "pendant": "#E8E4DA", "mirror": "#C3D3DC",
    }

    @staticmethod
    def _normalize_style(ftype: str, style: Optional[str]) -> Optional[str]:
        """Models return free-form styles; map them to what the editor renders."""
        style = (style or "").strip().lower() or None
        if not style:
            return None
        if ftype == "curtain":
            return "sheer" if any(k in style for k in ("sheer", "voile", "translucent")) else "solid"
        if ftype == "window":
            if "floor" in style or "full" in style:
                return "floor_to_ceiling"
            if "slid" in style:
                return "sliding_door"
            return "standard"
        return style

    def _measured_features(self, detection, geom) -> List[WallFeature]:
        features: List[WallFeature] = []
        for det in (detection.get("features") or [])[:10]:
            ftype = (det.get("type") or "").strip().lower()
            if ftype not in self.FEATURE_DEFAULTS:
                continue
            est = room_geometry.place_feature(geom, det["box"], ftype)
            if est is None:
                print(f"[SceneBuilder] Could not place {ftype} on a wall")
                continue
            style = self._normalize_style(ftype, det.get("style"))
            features.append(WallFeature(
                id=f"{ftype}_{uuid.uuid4().hex[:6]}",
                type=ftype,
                style=style,
                wall=est.wall,
                center_x_m=round(est.center_along, 3),
                center_z_m=round(est.center_z, 3),
                width_m=round(est.width, 3),
                height_m=round(est.height, 3),
                bottom_m=round(est.bottom, 3),
                color=det.get("color") if isinstance(det.get("color"), str) else self.FEATURE_DEFAULTS[ftype],
            ))
        return features

    def _projection(self, geom, hires) -> Optional[PhotoProjection]:
        """Mask of bare shell pixels, so the editor can project the photo onto walls/floor."""
        from .generation_service import generation_service

        try:
            mask = room_geometry.structure_mask_image(geom, hires.size)
            url = generation_service.save_texture(mask.convert("RGB"), "mask")
            return PhotoProjection(mask_url=url, width=hires.width, height=hires.height)
        except Exception as e:
            print(f"[SceneBuilder] Projection mask failed: {e}")
            return None

    async def _match_catalog(self, detection: Dict[str, Any]) -> None:
        """
        Pick each object's catalog entry. The shape matters for fidelity
        (an L-shaped sectional vs a straight sofa, a round vs a rectangular
        table), so labels are judged semantically with TypeSafe when it is
        configured; label rules otherwise. Non-furniture is flagged _skip.
        """
        objects = detection.get("objects") or []
        picks = await semantic_service.match_catalog(objects, detection.get("room_type") or "room")
        for det, pick in zip(objects, picks):
            if pick is not None:
                if pick == "none":
                    det["_skip"] = True
                else:
                    det["_entry_id"] = pick
                continue
            on_furniture = any(
                isinstance(r, dict) and (r.get("type") or "").lower() == "on"
                for r in det.get("relations") or []
            )
            entry = catalog_service.match_label(
                det.get("label") or "", det.get("category") or "", det.get("width_m"),
                on_furniture=on_furniture,
            )
            if entry:
                det["_entry_id"] = entry["id"]

    # ---------- layout-only fallback ----------

    def _layout_scene(self, detection, depth_map, image_size, hires) -> SceneData:
        """The vision model's floor plan, when the room can't be measured."""
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
            detection.get("objects") or [], depth_map, image_size, room,
        )

        return SceneData(
            room_type=detection.get("room_type") or "room",
            style=detection.get("style"),
            room=room,
            objects=objects,
            geometry={"source": "estimated"},
        )


scene_builder = SceneBuilder()
