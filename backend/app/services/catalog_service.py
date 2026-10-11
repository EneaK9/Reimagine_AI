"""
ReimagineAI - Furniture Catalog Service

Loads the procedural furniture catalog and matches detected furniture
(category + rough size) to the best catalog entry.
"""
from __future__ import annotations

import json
import os
from typing import Dict, List, Optional


class CatalogService:
    def __init__(self):
        data_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data")
        self.catalog_path = os.path.join(data_dir, "catalog", "catalog.json")
        self._catalog: Optional[dict] = None

    def _load(self) -> dict:
        if self._catalog is None:
            with open(self.catalog_path, "r", encoding="utf-8") as f:
                self._catalog = json.load(f)
        return self._catalog

    def get_catalog(self) -> dict:
        return self._load()

    def entries(self) -> List[dict]:
        return self._load()["entries"]

    def get_entry(self, entry_id: str) -> Optional[dict]:
        for entry in self.entries():
            if entry["id"] == entry_id:
                return entry
        return None

    def normalize_category(self, raw_category: str) -> str:
        """Map a free-form detected label to a canonical catalog category."""
        cat = (raw_category or "").strip().lower().replace("-", " ")
        aliases = self._load().get("category_aliases", {})
        known = {e["category"] for e in self.entries()}
        if cat in known:
            return cat
        if cat.replace(" ", "_") in known:
            return cat.replace(" ", "_")
        if cat in aliases:
            return aliases[cat]
        # Phrase fallback ("grey fabric sofa" -> "sofa"). English puts the
        # head noun last, so a match at the end wins ("table lamp" is a lamp,
        # not a table); among those, the longest phrase wins.
        phrases = {alias: target for alias, target in aliases.items()}
        phrases.update({c.replace("_", " "): c for c in known})
        matches = [(p, t) for p, t in phrases.items() if p in cat]
        if matches:
            suffix = [m for m in matches if cat.endswith(m[0])]
            return max(suffix or matches, key=lambda m: len(m[0]))[1]
        return cat  # unknown; editor renders a generic box

    def match(self, raw_category: str, approx_width_m: Optional[float] = None) -> Optional[dict]:
        """Best catalog entry for a detected item: same category, nearest width."""
        category = self.normalize_category(raw_category)
        candidates = [e for e in self.entries() if e["category"] == category]
        if not candidates:
            return None
        if approx_width_m is None or approx_width_m <= 0:
            return candidates[0]
        return min(candidates, key=lambda e: abs(e["dims_m"][0] - approx_width_m))

    def variants_for_category(self, category: str) -> List[dict]:
        return [e for e in self.entries() if e["category"] == category]

    # Shape words in a detected label -> builders that render that shape
    _SHAPES = (
        (("round", "circular", "oval", "circle", "drum"), {"table_round", "rug_round"}),
        (("l-shaped", "l shaped", "sectional", "corner sofa", "corner couch", "chaise"), {"sofa_l"}),
    )
    _SPECIAL = {"table_round", "rug_round", "sofa_l"}

    def match_label(
        self,
        label: str,
        raw_category: str,
        approx_width_m: Optional[float] = None,
        on_furniture: bool = False,
    ) -> Optional[dict]:
        """
        Best entry for a detected item using its label as well as its
        category: "round jute rug" gets the round rug, "grey L-shaped
        sectional" the L-shaped sofa, "office chair" the office chair.
        on_furniture: the item stands on other furniture (a lamp on a
        nightstand is a table lamp, whatever the category said).
        """
        known = {e["category"] for e in self.entries()}
        category = self.normalize_category(raw_category)
        if category not in known:
            category = self.normalize_category(label)
        try:
            small = 0 < float(approx_width_m or 0) < 0.33
        except (TypeError, ValueError):
            small = False
        if category == "lamp_floor" and (on_furniture or small):
            category = "lamp_table"
        candidates = [e for e in self.entries() if e["category"] == category]
        if not candidates:
            return None
        text = f"{label} {raw_category}".lower()
        preferred: List[dict] = []
        for words, builders in self._SHAPES:
            if any(w in text for w in words):
                preferred = [e for e in candidates if e.get("builder") in builders]
                break
        else:
            if any(w in text for w in ("office", "swivel", "desk chair", "gaming chair")):
                preferred = [e for e in candidates if e["id"] == "chair_office"]
            elif "king" in text:
                preferred = [e for e in candidates if e["id"] == "bed_king"]
            else:
                preferred = [e for e in candidates if e.get("builder") not in self._SPECIAL]
        pool = preferred or candidates
        try:
            width = float(approx_width_m or 0)
        except (TypeError, ValueError):
            width = 0.0
        if width <= 0:
            return pool[0]
        return min(pool, key=lambda e: abs(e["dims_m"][0] - width))


catalog_service = CatalogService()
