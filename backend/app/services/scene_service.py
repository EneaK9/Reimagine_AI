"""
ReimagineAI - Scene Service

Persistence + versioning + edit operations for structured 3D scenes.
Every mutation snapshots the previous state into scene_versions,
so undo/redo and history are simple version reverts.
"""
from __future__ import annotations

import copy
import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db.models import Scene as SceneRow
from ..db.models import SceneVersion as SceneVersionRow
from ..models.scene import (
    SceneData,
    SceneObject,
    SceneOp,
    SceneResponse,
    SceneSummary,
)
from .catalog_service import catalog_service
from .openai_service import openai_service

settings = get_settings()

MAX_VERSIONS_KEPT = 50

SHELL_TARGETS = {"wall", "walls", "floor", "ceiling"}

# Common color names for the rule-based edit fast path
COLOR_MAP = {
    "black": "#1A1A1C", "white": "#F5F5F2", "grey": "#8E8E8E", "gray": "#8E8E8E",
    "light grey": "#C9C9C9", "light gray": "#C9C9C9", "dark grey": "#4A4A4C",
    "dark gray": "#4A4A4C", "red": "#B03A2E", "dark red": "#7B241C",
    "blue": "#2E5A8F", "navy": "#1F3A5F", "navy blue": "#1F3A5F",
    "light blue": "#7FA8D0", "sky blue": "#87BEE0", "teal": "#2E7F7A",
    "green": "#3E7C4F", "dark green": "#2C5F3E", "forest green": "#2C5F3E",
    "olive": "#6B7C3E", "sage": "#9CAF88", "mint": "#A8D5BA",
    "yellow": "#D9B93B", "mustard": "#C9A227", "orange": "#C87533",
    "brown": "#7C5E42", "dark brown": "#5A4030", "beige": "#D9CDB8",
    "cream": "#EFE8D8", "tan": "#C8A97C", "pink": "#D98BA6", "purple": "#7B5EA7",
    "violet": "#8A63B8", "gold": "#C9A227", "turquoise": "#40B5AD",
    "burgundy": "#6E1E2B", "maroon": "#6E1E2B", "charcoal": "#36383B",
    "ivory": "#F4EFE3", "off white": "#F0EBE0", "lavender": "#B9A7D9",
}


class SceneServiceError(ValueError):
    pass


class SceneService:
    # ---------- CRUD ----------

    def _get_row(self, db: Session, scene_id: str, user_id: Optional[str] = None) -> Optional[SceneRow]:
        stmt = select(SceneRow).where(SceneRow.id == scene_id)
        if user_id:
            stmt = stmt.where(SceneRow.user_id == user_id)
        return db.scalar(stmt)

    def _to_response(self, row: SceneRow) -> SceneResponse:
        return SceneResponse(
            scene_id=row.id,
            title=row.title,
            version=row.version,
            data=SceneData.model_validate(row.data),
            conversation_id=row.conversation_id,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def create_scene(
        self,
        db: Session,
        user_id: str,
        data: SceneData,
        conversation_id: Optional[str] = None,
        title: Optional[str] = None,
    ) -> SceneResponse:
        row = SceneRow(
            id=f"scene_{uuid.uuid4().hex[:12]}",
            user_id=user_id,
            conversation_id=conversation_id,
            title=title or f"{data.room_type.title()} Scene",
            version=1,
            data=data.model_dump(),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return self._to_response(row)

    def get_scene(self, db: Session, scene_id: str, user_id: Optional[str] = None) -> Optional[SceneResponse]:
        row = self._get_row(db, scene_id, user_id)
        return self._to_response(row) if row else None

    def list_scenes(self, db: Session, user_id: str, limit: int = 50) -> List[SceneSummary]:
        stmt = (
            select(SceneRow)
            .where(SceneRow.user_id == user_id)
            .order_by(SceneRow.updated_at.desc())
            .limit(limit)
        )
        rows = db.scalars(stmt).all()
        return [
            SceneSummary(
                scene_id=r.id,
                title=r.title,
                version=r.version,
                room_type=(r.data or {}).get("room_type", "room"),
                object_count=len((r.data or {}).get("objects", [])),
                updated_at=r.updated_at,
            )
            for r in rows
        ]

    def delete_scene(self, db: Session, scene_id: str, user_id: str) -> bool:
        row = self._get_row(db, scene_id, user_id)
        if not row:
            return False
        db.delete(row)
        db.commit()
        return True

    # ---------- versioning ----------

    def _snapshot(self, db: Session, row: SceneRow) -> None:
        db.add(SceneVersionRow(scene_id=row.id, version=row.version, data=copy.deepcopy(row.data)))
        # Trim old snapshots
        versions = db.scalars(
            select(SceneVersionRow)
            .where(SceneVersionRow.scene_id == row.id)
            .order_by(SceneVersionRow.version.desc())
        ).all()
        for stale in versions[MAX_VERSIONS_KEPT:]:
            db.delete(stale)

    def list_versions(self, db: Session, scene_id: str, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        row = self._get_row(db, scene_id, user_id)
        if not row:
            return []
        versions = db.scalars(
            select(SceneVersionRow)
            .where(SceneVersionRow.scene_id == scene_id)
            .order_by(SceneVersionRow.version.desc())
        ).all()
        return [
            {"version": v.version, "created_at": v.created_at.isoformat()}
            for v in versions
        ]

    def revert(self, db: Session, scene_id: str, version: int, user_id: Optional[str] = None) -> Optional[SceneResponse]:
        row = self._get_row(db, scene_id, user_id)
        if not row:
            return None
        snapshot = db.scalar(
            select(SceneVersionRow).where(
                SceneVersionRow.scene_id == scene_id,
                SceneVersionRow.version == version,
            )
        )
        if not snapshot:
            return None
        self._snapshot(db, row)
        row.data = copy.deepcopy(snapshot.data)
        row.version += 1
        row.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(row)
        return self._to_response(row)

    # ---------- edit operations ----------

    def apply_ops(
        self,
        db: Session,
        scene_id: str,
        ops: List[SceneOp],
        user_id: Optional[str] = None,
    ) -> SceneResponse:
        row = self._get_row(db, scene_id, user_id)
        if not row:
            raise SceneServiceError(f"Scene {scene_id} not found")

        data = copy.deepcopy(row.data)
        for op in ops:
            self._apply_op(data, op)

        # Validate before persisting
        SceneData.model_validate(data)

        self._snapshot(db, row)
        row.data = data
        row.version += 1
        row.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(row)
        return self._to_response(row)

    def _find_object(self, data: dict, target: str) -> Optional[dict]:
        for obj in data.get("objects", []):
            if obj["id"] == target:
                return obj
        # Category fallback: first object of that category ("sofa" targets sofa_ab12cd)
        normalized = catalog_service.normalize_category(target)
        for obj in data.get("objects", []):
            if obj["category"] == normalized:
                return obj
        return None

    def _apply_op(self, data: dict, op: SceneOp) -> None:
        kind = op.op
        value = op.value or {}

        if kind == "set_room":
            room = data["room"]
            for key in ("width_m", "depth_m", "height_m"):
                if key in value:
                    room[key] = float(value[key])
            for mat_key, mat_name in (
                ("wall_color", "wall_material"),
                ("floor_color", "floor_material"),
                ("ceiling_color", "ceiling_material"),
            ):
                if mat_key in value:
                    room[mat_name]["color"] = value[mat_key]
            return

        if kind == "add":
            obj = value.get("object")
            if not obj:
                raise SceneServiceError("add op requires value.object")
            SceneObject.model_validate(obj)
            data.setdefault("objects", []).append(obj)
            return

        if not op.target:
            raise SceneServiceError(f"op '{kind}' requires a target")

        # Wall features (windows/doors/curtains) addressed by id
        if kind in ("recolor", "material"):
            for feature in (data["room"].get("features") or []):
                if feature["id"] == op.target:
                    if "color" in value:
                        feature["color"] = value["color"]
                    return

        # Shell material edits addressed as wall/floor/ceiling
        if op.target.lower() in SHELL_TARGETS and kind in ("recolor", "material"):
            key = "wall_material" if op.target.lower().startswith("wall") else f"{op.target.lower()}_material"
            material = data["room"].get(key)
            if material is None:
                raise SceneServiceError(f"Unknown shell target {op.target}")
            if "color" in value:
                material["color"] = value["color"]
            if "texture" in value:
                material["texture"] = value["texture"]
            return

        obj = self._find_object(data, op.target)
        if obj is None:
            raise SceneServiceError(f"Object '{op.target}' not found in scene")

        if kind == "move":
            pos = value.get("pos")
            if not pos or len(pos) != 3:
                raise SceneServiceError("move op requires value.pos [x,y,z]")
            obj["transform"]["pos"] = [float(v) for v in pos]
        elif kind == "rotate":
            obj["transform"]["rot_y_deg"] = float(value.get("rot_y_deg", 0.0))
        elif kind == "scale":
            scale = value.get("scale")
            if not scale or len(scale) != 3:
                raise SceneServiceError("scale op requires value.scale [x,y,z]")
            obj["transform"]["scale"] = [float(v) for v in scale]
        elif kind in ("recolor", "material"):
            override = obj.get("material_override") or {}
            if "color" in value:
                override["color"] = value["color"]
            if "texture" in value:
                override["texture"] = value["texture"]
            obj["material_override"] = override
        elif kind == "swap":
            ref = value.get("ref")
            entry = catalog_service.get_entry(ref) if ref else None
            if not entry:
                raise SceneServiceError(f"swap op: unknown catalog ref '{ref}'")
            obj["asset"] = {"type": "catalog", "ref": entry["id"]}
            obj["category"] = entry["category"]
            obj["dimensions_m"] = list(entry["dims_m"])
            obj["label"] = entry["name"]
        elif kind == "remove":
            data["objects"] = [o for o in data["objects"] if o["id"] != obj["id"]]
        else:
            raise SceneServiceError(f"Unknown op '{kind}'")

    def update_asset_refs(
        self,
        db: Session,
        scene_id: str,
        asset_urls: Dict[str, str],
        user_id: Optional[str] = None,
    ) -> Optional["SceneResponse"]:
        """Swap objects' assets to generated GLB URLs (one version bump)."""
        row = self._get_row(db, scene_id, user_id)
        if not row:
            return None
        data = copy.deepcopy(row.data)
        for obj in data.get("objects", []):
            url = asset_urls.get(obj["id"])
            if url:
                obj["asset"] = {"type": "url", "ref": url}
        SceneData.model_validate(data)
        self._snapshot(db, row)
        row.data = data
        row.version += 1
        row.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(row)
        return self._to_response(row)

    # ---------- natural-language editing ----------

    def _rule_based_shell_ops(self, instruction: str) -> List[SceneOp]:
        """
        Deterministic fast path for wall/floor/ceiling recolors
        ("make the walls black") — too important to leave to the LLM.
        Returns ops only when the WHOLE instruction is shell recolors.
        """
        import re

        text = instruction.lower().strip()
        shell_words = {"wall": "wall", "walls": "wall", "floor": "floor", "ceiling": "ceiling"}
        # Bail out if any furniture-ish word appears — let the LLM handle it
        mentions_other = re.search(
            r"\b(sofa|couch|chair|table|bed|lamp|rug|plant|mirror|shelf|shelves|"
            r"wardrobe|dresser|desk|tv|ottoman|furniture|move|swap|remove|add|rotate)\b",
            text,
        )
        if mentions_other:
            return []

        ops: List[SceneOp] = []
        # Segment on "and" / commas so "walls black and floor white" works
        for segment in re.split(r"\band\b|,|;", text):
            target = next(
                (canon for word, canon in shell_words.items()
                 if re.search(rf"\b{word}\b", segment)),
                None,
            )
            if not target:
                continue
            # Longest color names first ("navy blue" before "blue")
            for name in sorted(COLOR_MAP, key=len, reverse=True):
                if name in segment:
                    ops.append(SceneOp(op="recolor", target=target,
                                       value={"color": COLOR_MAP[name]}))
                    break
            else:
                hex_match = re.search(r"#[0-9a-f]{6}", segment)
                if hex_match:
                    ops.append(SceneOp(op="recolor", target=target,
                                       value={"color": hex_match.group(0).upper()}))
        return ops

    async def parse_nl_edit(self, data: dict, instruction: str) -> List[SceneOp]:
        """Turn 'make the sofa navy and move it to the back wall' into SceneOps."""
        # Deterministic path for pure shell recolors
        rule_ops = self._rule_based_shell_ops(instruction)
        if rule_ops:
            print(f"[SceneService] Rule-based shell edit: {len(rule_ops)} op(s)")
            return rule_ops
        objects_desc = [
            {
                "id": o["id"],
                "category": o["category"],
                "label": o.get("label", ""),
                "pos": o["transform"]["pos"],
                "color": (o.get("material_override") or {}).get("color"),
            }
            for o in data.get("objects", [])
        ]
        room = data.get("room", {})
        catalog_ids = [e["id"] for e in catalog_service.entries()]

        system_prompt = f"""You convert interior-design edit requests into JSON operations for a 3D scene.

The room: width_m={room.get('width_m')}, depth_m={room.get('depth_m')}, height_m={room.get('height_m')}.
Coordinates: room centered at origin. x in [-width/2, +width/2] (left to right),
z in [-depth/2, +depth/2] (back wall at -depth/2, front/camera at +depth/2). y=0 is the floor.

Objects currently in the scene:
{json.dumps(objects_desc, indent=1)}

Available catalog asset ids (for swap/add): {catalog_ids}

Return ONLY a JSON object {{"ops": [...]}} with no prose. Each operation is one of:
{{"op":"move","target":"<object id>","value":{{"pos":[x,0,z]}}}}
{{"op":"rotate","target":"<object id>","value":{{"rot_y_deg":90}}}}
{{"op":"recolor","target":"<object id or wall/floor/ceiling>","value":{{"color":"#1F3A5F"}}}}
{{"op":"swap","target":"<object id>","value":{{"ref":"<catalog id>"}}}}
{{"op":"remove","target":"<object id>","value":{{}}}}
{{"op":"add","value":{{"object":{{"id":"<category>_new1","category":"<category>","label":"<name>","asset":{{"type":"catalog","ref":"<catalog id>"}},"transform":{{"pos":[x,0,z],"rot_y_deg":0,"scale":[1,1,1]}},"dimensions_m":[w,h,d]}}}}}}
{{"op":"set_room","value":{{"wall_color":"#EEE8DD"}}}}

CRITICAL rules:
- When the user says "wall"/"walls", target is EXACTLY "wall". "floor" -> "floor",
  "ceiling" -> "ceiling". NEVER apply a wall/floor/ceiling request to furniture.
- Otherwise target MUST be an exact object id from the list above.
- Colors as hex. "navy" -> "#1F3A5F", "forest green" -> "#2C5F3E", etc.
- Keep positions inside the room bounds.
- If the request is ambiguous, choose the most likely single interpretation.
- If the request cannot be done, return {{"ops": []}}.

Examples:
"make the walls black" -> {{"ops":[{{"op":"recolor","target":"wall","value":{{"color":"#1A1A1C"}}}}]}}
"make the bed blue and move it to the back wall" (bed id bed_a1b2c3, room depth 4) ->
{{"ops":[{{"op":"recolor","target":"bed_a1b2c3","value":{{"color":"#2E5A8F"}}}},{{"op":"move","target":"bed_a1b2c3","value":{{"pos":[0,0,-0.9]}}}}]}}"""

        response = await openai_service.client.chat.completions.create(
            model=settings.gpt_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": instruction},
            ],
            max_tokens=1200,
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        text = response.choices[0].message.content.strip()
        parsed = json.loads(text)
        raw_ops = parsed.get("ops", parsed if isinstance(parsed, list) else [])
        return [SceneOp.model_validate(o) for o in raw_ops]

    async def nl_edit(
        self,
        db: Session,
        scene_id: str,
        instruction: str,
        user_id: Optional[str] = None,
    ) -> tuple[Optional[SceneResponse], List[SceneOp], str]:
        row = self._get_row(db, scene_id, user_id)
        if not row:
            return None, [], "Scene not found"

        ops = await self.parse_nl_edit(row.data, instruction)
        if not ops:
            return self._to_response(row), [], (
                "I couldn't map that request to a 3D edit. Try something like "
                "\"move the sofa to the back wall\" or \"make the walls light grey\"."
            )

        applied: List[SceneOp] = []
        data = copy.deepcopy(row.data)
        errors: List[str] = []
        for op in ops:
            try:
                self._apply_op(data, op)
                applied.append(op)
            except SceneServiceError as e:
                errors.append(str(e))

        if not applied:
            return self._to_response(row), [], f"Couldn't apply the edit: {'; '.join(errors)}"

        SceneData.model_validate(data)
        self._snapshot(db, row)
        row.data = data
        row.version += 1
        row.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(row)

        summary = f"Applied {len(applied)} change(s) to your 3D room."
        if errors:
            summary += f" (Skipped: {'; '.join(errors)})"
        return self._to_response(row), applied, summary


scene_service = SceneService()
