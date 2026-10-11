"""
ReimagineAI - Semantic judgments (TypeSafe System One)

Small typed language judgments where plain code needs common sense but a
generative LLM round-trip would be slow or unreliable:

- match_catalog: which catalog shape represents a detected item
  ("grey L-shaped sectional" -> sofa_l_shape, "round jute rug" -> rug_round,
  "sheer curtain" -> none).
- route_chat: is a chat message asking to change the room, confirming a
  suggestion, or just asking a question — and can it apply to the 3D scene?
- parse_scene_edit: simple 3D edits ("make the sofa navy", "remove the rug")
  -> typed ops, grounded in the scene's real object ids. Anything multi-step
  or uncertain returns None and goes to the GPT parser.

TypeSafe's Jev model answers Choice/Noul questions with probabilities and
confidence; code keeps the policy (thresholds, fallbacks). Every function
returns None/fallback values when TYPESAFE_API_KEY is unset or the call
fails, so the app never depends on it. Jev is text-only and weak at numbers,
so sizes are passed as words and geometry stays in code.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..config import get_settings
from .catalog_service import catalog_service

settings = get_settings()

# Related categories a detection may really belong to (fixes near-misses
# like "bench" vs "ottoman" while keeping option lists short).
RELATED = {
    "sofa": {"sofa", "armchair", "bench", "ottoman"},
    "armchair": {"armchair", "sofa", "chair"},
    "chair": {"chair", "armchair", "stool"},
    "stool": {"stool", "chair", "ottoman"},
    "ottoman": {"ottoman", "bench", "stool"},
    "bench": {"bench", "ottoman", "sofa"},
    "table": {"table", "coffee_table", "desk", "side_table", "console"},
    "coffee_table": {"coffee_table", "table", "side_table", "ottoman"},
    "side_table": {"side_table", "nightstand", "coffee_table"},
    "nightstand": {"nightstand", "side_table", "dresser"},
    "desk": {"desk", "table", "console"},
    "console": {"console", "sideboard", "desk", "table"},
    "sideboard": {"sideboard", "console", "dresser", "tv_stand"},
    "dresser": {"dresser", "sideboard", "wardrobe", "nightstand"},
    "wardrobe": {"wardrobe", "dresser", "bookshelf"},
    "bookshelf": {"bookshelf", "wardrobe"},
    "tv_stand": {"tv_stand", "sideboard", "console"},
    "lamp_floor": {"lamp_floor", "lamp_table"},
    "lamp_table": {"lamp_table", "lamp_floor"},
    "kitchen_cabinet": {"kitchen_cabinet", "kitchen_island", "sideboard"},
    "kitchen_island": {"kitchen_island", "kitchen_cabinet", "table"},
}

BUILDER_SHAPES = {
    "sofa": "straight sofa with a back and two arms",
    "sofa_l": "L-shaped corner sofa / sectional with a chaise",
    "armchair": "single-seat upholstered armchair",
    "chair": "chair on legs with a backrest",
    "table": "rectangular table on four legs",
    "table_round": "round or oval table on a central pedestal",
    "bed": "bed with headboard, mattress and bedding",
    "cabinet": "box-shaped cabinet with doors or drawers",
    "bookshelf": "open shelving unit / bookcase",
    "tv": "flat-screen television",
    "lamp_floor": "tall floor lamp with a shade",
    "lamp_table": "small table lamp with a shade",
    "rug": "rectangular rug",
    "rug_round": "round or oval rug",
    "plant": "potted plant",
    "mirror": "free-standing floor mirror",
    "ottoman": "low upholstered ottoman, pouf or bench seat",
    "stool": "stool without a backrest",
    "fridge": "refrigerator",
    "stove": "stove / oven",
    "sink": "sink or bathroom vanity",
    "toilet": "toilet",
    "bathtub": "bathtub",
    "shower": "shower enclosure",
    "washer": "washing machine or dryer",
}

NOT_FURNITURE = (
    "Not free-standing floor furniture a catalog model can represent: curtains, "
    "windows, doors, wall art, wall shelves, pillows, blankets, small decor"
)


def _size_words(width_m: Optional[float]) -> str:
    try:
        w = float(width_m or 0)
    except (TypeError, ValueError):
        w = 0.0
    if w <= 0:
        return "unknown size"
    if w < 0.5:
        return "very small (under 0.5 m wide)"
    if w < 1.0:
        return "small (0.5 to 1 m wide)"
    if w < 1.8:
        return "medium (1 to 1.8 m wide)"
    if w < 2.5:
        return "large (1.8 to 2.5 m wide)"
    return "very large (over 2.5 m wide)"


@dataclass
class ChatRoute:
    intent: str                 # change_room | confirm_suggestion | question_or_chat | other
    intent_confidence: float
    scene_edit: float           # P(message asks for a change applicable to the 3D room)


class SemanticService:
    def __init__(self):
        self._client = None
        self._loop = None

    @property
    def enabled(self) -> bool:
        return bool(settings.typesafe_api_key)

    def _get_client(self):
        """One client per event loop (the HTTP client is bound to its loop)."""
        loop = asyncio.get_running_loop()
        if self._client is None or self._loop is not loop:
            from typesafe_sdk import AsyncTypeSafeClient, RetryPolicy

            self._client = AsyncTypeSafeClient(
                api_key=settings.typesafe_api_key,
                model=settings.typesafe_model,
                timeout=6.0,
                retry=RetryPolicy(max_retries=1, backoff_initial=0.3, backoff_max=1.0),
            )
            self._loop = loop
        return self._client

    async def _ask(self, state: Any, questions: Dict[str, Any]):
        if not self.enabled or not questions:
            return None
        try:
            return await self._get_client().system_one(state=state, questions=questions)
        except Exception as e:
            print(f"[Semantic] TypeSafe request failed, using rules: {e!r}")
        return None

    # ---------- catalog shapes ----------

    async def match_catalog(self, objects: List[Dict[str, Any]], room_type: str) -> List[Optional[str]]:
        """
        Per detected object: a catalog entry id, "none" (not modelable
        furniture — skip it), or None (no confident judgment: use rules).
        Never raises: any failure means "use rules".
        """
        try:
            return await self._match_catalog(objects, str(room_type or "room"))
        except Exception as e:
            print(f"[Semantic] Catalog matching failed, using rules: {e!r}")
            return [None] * len(objects)

    async def _match_catalog(self, objects: List[Dict[str, Any]], room_type: str) -> List[Optional[str]]:
        results: List[Optional[str]] = [None] * len(objects)
        if not self.enabled or not objects:
            return results
        from typesafe_sdk import Choice

        entries = catalog_service.entries()
        items, questions, options = [], {}, {}
        for i, det in enumerate(objects[:20]):
            label = str(det.get("label") or det.get("category") or "")
            category = catalog_service.normalize_category(str(det.get("category") or label))
            family = RELATED.get(category, {category})
            candidates = [e for e in entries if e["category"] in family] or entries
            items.append({
                "label": label,
                "category_guess": det.get("category"),
                "size": _size_words(det.get("width_m")),
            })
            criteria = {
                e["id"]: f"{e['name']}: {BUILDER_SHAPES.get(e.get('builder'), e.get('builder'))}, "
                         f"typically {_size_words(e['dims_m'][0])}"
                for e in candidates
            }
            criteria["none"] = NOT_FURNITURE
            options[i] = set(criteria)
            questions[f"item_{i}"] = Choice(
                instructions=(
                    f"Which catalog model best represents `items[{i}]` in this {room_type}? "
                    "Match its shape words (round, oval, L-shaped, sectional, corner, office, "
                    "swivel, king-size, single...) and its size."
                ),
                criteria=criteria,
            )
        response = await self._ask({"room_type": room_type, "items": items}, questions)
        if response is None:
            return results
        for i in range(len(items)):
            answer = response.choices.get(f"item_{i}")
            if answer is None or answer.choice not in options[i]:
                continue
            if answer.choice == "none":
                if answer.confidence >= 0.75:
                    results[i] = "none"
            elif answer.confidence >= 0.5:
                results[i] = answer.choice
        picked = sum(1 for r in results if r)
        print(f"[Semantic] Catalog shapes: {picked}/{len(items)} confident picks")
        return results

    # ---------- chat routing ----------

    async def route_chat(
        self,
        message: str,
        previous_assistant: Optional[str],
        has_photo: bool,
        has_scene: bool,
    ) -> Optional[ChatRoute]:
        """Classify a chat message; None when TypeSafe is unavailable. Never raises."""
        try:
            return await self._route_chat(message, previous_assistant, has_photo, has_scene)
        except Exception as e:
            print(f"[Semantic] Chat routing failed, using keyword rules: {e!r}")
            return None

    async def _route_chat(self, message, previous_assistant, has_photo, has_scene) -> Optional[ChatRoute]:
        if not self.enabled or not message.strip():
            return None
        from typesafe_sdk import Choice, Noul

        state = {
            "message": message[:2000],
            "previous_assistant_message": (previous_assistant or "")[-1500:],
            "user_has_room_photo": has_photo,
            "user_has_3d_room": has_scene,
        }
        questions = {
            "intent": Choice(
                instructions="What does the user want with `message`?",
                criteria={
                    "change_room": {
                        "what": "Asks to change or visualize a different look of their room now: colors, "
                                "materials, style, lighting, adding/removing/moving/replacing furniture.",
                        "examples": ["make the walls sage green", "add a plant by the window",
                                     "show it in Scandinavian style", "remove the rug"],
                    },
                    "confirm_suggestion": {
                        "what": "Agrees to apply a change the assistant proposed in "
                                "`previous_assistant_message`.",
                        "examples": ["yes", "do it", "sounds good, go ahead", "ok apply that"],
                    },
                    "question_or_chat": {
                        "what": "Asks a question, wants advice, ideas or information, or chats, "
                                "without asking to apply a change right now.",
                        "not_for": "Requests to show or apply a new look.",
                        "examples": ["what style is my bedroom?", "which colors go with oak floors?",
                                     "thanks!"],
                    },
                    "other": "Anything else.",
                },
            ),
            "scene_edit": Noul(
                instructions=(
                    "Does `message` ask for a concrete change that can be applied to a 3D model of "
                    "the room: recoloring walls, floor, ceiling or furniture, or moving, rotating, "
                    "adding, removing or replacing furniture?"
                ),
            ),
        }
        response = await self._ask(state, questions)
        if response is None:
            return None
        intent = response.choices.get("intent")
        edit = response.nouls.get("scene_edit")
        if intent is None or edit is None:
            return None
        return ChatRoute(intent=intent.choice, intent_confidence=intent.confidence, scene_edit=edit.noul)

    # ---------- simple 3D edits ----------

    async def parse_scene_edit(
        self,
        instruction: str,
        objects: List[Dict[str, Any]],
        color_names: List[str],
    ) -> Optional[Dict[str, Any]]:
        """
        Speculative fan-out over one request: the action, its target object
        and its color/rotation arguments. Returns {"action", "target",
        "color", "rotate_deg"} when every judgment used is confident, else
        None (the caller falls back to the GPT parser). Never raises.
        """
        try:
            return await self._parse_scene_edit(instruction, objects, color_names)
        except Exception as e:
            print(f"[Semantic] Edit parsing failed, using the GPT parser: {e!r}")
            return None

    async def _parse_scene_edit(self, instruction, objects, color_names) -> Optional[Dict[str, Any]]:
        if not self.enabled or not instruction.strip():
            return None
        from typesafe_sdk import Choice, Noul

        targets = {
            o["id"]: {"label": o.get("label") or o["category"], "category": o["category"],
                      "position": o.get("where") or "", "color": o.get("color_name") or ""}
            for o in objects[:60]
        }
        targets["none"] = "The instruction does not refer to a single furniture object."
        questions = {
            "action": Choice(
                instructions="Which single edit does `instruction` ask for?",
                criteria={
                    "recolor_object": "Change the color of one furniture object.",
                    "recolor_walls": "Change the wall color.",
                    "recolor_floor": "Change the floor color.",
                    "recolor_ceiling": "Change the ceiling color.",
                    "remove_object": "Remove / delete one furniture object.",
                    "rotate_object": "Turn / rotate one furniture object in place.",
                    "other": {
                        "what": "Anything else: moving or adding furniture, swapping models, "
                                "several changes at once, style changes, unclear requests.",
                    },
                },
            ),
            "target": Choice(
                instructions="Which furniture object in `objects` does `instruction` refer to?",
                criteria=targets,
            ),
            "color": Choice(
                instructions="Which color does `instruction` ask for?",
                criteria={**{name: None for name in color_names},
                          "other": "No color, or a color not in this list."},
            ),
            "rotation": Choice(
                instructions="How far does `instruction` ask to rotate the object?",
                criteria={
                    "quarter_left": "A quarter turn to the left / counterclockwise (90 degrees).",
                    "quarter_right": "A quarter turn to the right / clockwise (90 degrees).",
                    "half": "Turn it around / face the other way (180 degrees).",
                    "unspecified": "No rotation, or an amount not listed.",
                },
            ),
            "multiple": Noul(instructions="Does `instruction` ask for more than one change?"),
        }
        state = {
            "instruction": instruction[:1000],
            "objects": [{"id": k, **v} for k, v in targets.items() if k != "none"],
        }
        response = await self._ask(state, questions)
        if response is None:
            return None
        action = response.choices.get("action")
        multiple = response.nouls.get("multiple")
        if action is None or multiple is None or multiple.noul > 0.3:
            return None
        if action.choice == "other" or action.confidence < 0.75:
            return None
        result: Dict[str, Any] = {"action": action.choice}
        if action.choice.endswith("_object"):
            target = response.choices.get("target")
            if target is None or target.choice == "none" or target.confidence < 0.75:
                return None
            result["target"] = target.choice
        if action.choice.startswith("recolor"):
            color = response.choices.get("color")
            if color is None or color.choice == "other" or color.confidence < 0.7:
                return None
            result["color"] = color.choice
        if action.choice == "rotate_object":
            rotation = response.choices.get("rotation")
            degrees = {"quarter_left": 90.0, "quarter_right": -90.0, "half": 180.0}
            if rotation is None or rotation.choice not in degrees or rotation.confidence < 0.7:
                return None
            result["rotate_deg"] = degrees[rotation.choice]
        return result


semantic_service = SemanticService()
