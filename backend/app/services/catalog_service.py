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
        cat = (raw_category or "").strip().lower()
        aliases = self._load().get("category_aliases", {})
        if cat in aliases:
            return aliases[cat]
        known = {e["category"] for e in self.entries()}
        if cat in known:
            return cat
        # Substring fallback ("grey fabric sofa" -> "sofa")
        for alias, target in aliases.items():
            if alias in cat:
                return target
        for category in sorted(known, key=len, reverse=True):
            if category.replace("_", " ") in cat or category in cat:
                return category
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


catalog_service = CatalogService()
