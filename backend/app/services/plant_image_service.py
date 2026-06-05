"""
Plant image lookup service (Wikimedia/Wikipedia).

Purpose: Given a plant's botanical/common name, fetch a representative thumbnail URL
to display in the runner UI. Uses caching + concurrency limiting to stay fast/safe.
"""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass
from typing import Dict, Optional

import httpx

from ..config import get_settings


WIKIMEDIA_API_URL = "https://en.wikipedia.org/w/api.php"
SERPAPI_URL = "https://serpapi.com/search.json"
WIKIMEDIA_THUMB_SIZE = 600
WIKIMEDIA_MAX_CONCURRENCY = 3
WIKIMEDIA_CACHE_TTL_SECONDS = 60 * 60 * 24  # 24h

settings = get_settings()


@dataclass
class _CacheEntry:
    url: str
    expires_at: float


class PlantImageService:
    def __init__(self):
        self._sem = asyncio.Semaphore(WIKIMEDIA_MAX_CONCURRENCY)
        self._cache: Dict[str, _CacheEntry] = {}
        self.api_key = settings.serp_api_key

    def _get_cached(self, key: str) -> Optional[str]:
        entry = self._cache.get(key)
        if not entry:
            return None
        if time.time() >= entry.expires_at:
            self._cache.pop(key, None)
            return None
        return entry.url

    def _set_cached(self, key: str, url: str) -> None:
        self._cache[key] = _CacheEntry(
            url=url,
            expires_at=time.time() + WIKIMEDIA_CACHE_TTL_SECONDS,
        )

    async def get_plant_image_url(
        self,
        *,
        botanical_name: str = "",
        common_name: str = "",
    ) -> str:
        """
        Return a Wikimedia thumbnail URL (or empty string if not found).

        Strategy:
        - Try botanical name first, then common name.
        - Use a single generator=search query with prop=pageimages.
        """
        candidates = self._build_candidates(botanical_name, common_name)
        if not candidates:
            return ""

        async with httpx.AsyncClient(
            timeout=15,
            headers={
                "User-Agent": "ReimagineAI/1.0 (plant image lookup; https://example.com)",
            },
        ) as client:
            for query in candidates:
                cache_key = f"wiki:{query.lower()}"
                cached = self._get_cached(cache_key)
                if cached is not None:
                    return cached

                url = await self._fetch_thumbnail_url(client=client, query=query)
                if url:
                    self._set_cached(cache_key, url)
                    return url

            if self.api_key:
                for query in candidates:
                    cache_key = f"serp:{query.lower()}"
                    cached = self._get_cached(cache_key)
                    if cached is not None:
                        return cached

                    url = await self._fetch_serpapi_image_url(client=client, query=query)
                    if url:
                        self._set_cached(cache_key, url)
                        return url

        return ""

    def _build_candidates(self, botanical_name: str, common_name: str) -> list[str]:
        raw_candidates = [botanical_name.strip(), common_name.strip()]
        candidates: list[str] = []

        for candidate in raw_candidates:
            if not candidate:
                continue
            candidates.append(candidate)

            # Cultivar names like "Rosmarinus officinalis 'Tuscan Blue'" often
            # have no page image. The species page is much more reliable.
            without_cultivar = re.sub(r"\s+['\"].*?['\"]", "", candidate).strip()
            if without_cultivar and without_cultivar != candidate:
                candidates.append(without_cultivar)

            normalized = re.sub(r"\b(subsp|ssp|var|cv|f)\.?\b.*$", "", without_cultivar, flags=re.IGNORECASE).strip()
            if normalized and normalized != without_cultivar:
                candidates.append(normalized)

            species_name = self._species_name(normalized or without_cultivar)
            if species_name and species_name != candidate:
                candidates.append(species_name)

        # Common botanical synonym for rosemary.
        normalized = [c.lower() for c in candidates]
        if "rosmarinus officinalis" in normalized:
            candidates.append("Salvia rosmarinus")

        unique: list[str] = []
        seen = set()
        for candidate in candidates:
            key = candidate.lower()
            if key in seen:
                continue
            seen.add(key)
            unique.append(candidate)
        return unique

    def _species_name(self, candidate: str) -> str:
        parts = re.findall(r"[A-Za-z]+", candidate)
        if len(parts) < 2:
            return ""
        return f"{parts[0]} {parts[1]}"

    async def _fetch_thumbnail_url(self, *, client: httpx.AsyncClient, query: str) -> str:
        params = {
            "action": "query",
            "format": "json",
            "generator": "search",
            "gsrsearch": query,
            "gsrlimit": 5,
            "gsrnamespace": 0,
            "prop": "pageimages",
            "piprop": "thumbnail",
            "pithumbsize": WIKIMEDIA_THUMB_SIZE,
            "redirects": 1,
        }

        async with self._sem:
            try:
                response = await client.get(WIKIMEDIA_API_URL, params=params)
                response.raise_for_status()
                data = response.json()
            except Exception:
                return ""

        pages = ((data or {}).get("query") or {}).get("pages") or {}
        if not pages:
            return ""

        # pages is a dict keyed by pageid string. Choose the first search result
        # that actually has a thumbnail instead of assuming result #1 does.
        sorted_pages = sorted(pages.values(), key=lambda page: page.get("index", 999))
        for page in sorted_pages:
            thumb = (page or {}).get("thumbnail") or {}
            source = str(thumb.get("source") or "").strip()
            if source:
                return source
        return ""

    async def _fetch_serpapi_image_url(self, *, client: httpx.AsyncClient, query: str) -> str:
        params = {
            "engine": "google_images",
            "q": f"{query} plant flower",
            "api_key": self.api_key,
            "ijn": "0",
        }

        async with self._sem:
            try:
                response = await client.get(SERPAPI_URL, params=params)
                response.raise_for_status()
                data = response.json()
            except Exception as exc:
                print(f"SerpAPI plant image lookup failed for '{query}': {exc}")
                return ""

        for item in data.get("images_results", [])[:10]:
            source = str(
                item.get("original")
                or item.get("thumbnail")
                or item.get("source")
                or ""
            ).strip()
            if source.startswith("http"):
                return source
        return ""


plant_image_service = PlantImageService()

