"""
ReimagineAI - Product Search Service
Searches retailer product pages through SerpApi and normalizes the results.
"""
import asyncio
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import httpx

from ..config import get_settings
from ..models.schemas import ProductResult, StoreName
from .product_search_validators import (
    build_broadened_query,
    parse_search_intent,
    validate_product,
)


settings = get_settings()


class ProductSearchService:
    """
    Service for searching product links across supported retailers.
    """

    SERPAPI_URL = "https://serpapi.com/search.json"
    MAX_SEARCH_ATTEMPTS = 2
    TARGET_VALID_RESULTS = 10
    OVERFETCH_MULTIPLIER = 3
    MAX_FETCH_LIMIT = 25

    STORE_DOMAINS = {
        StoreName.AMAZON: "amazon.com",
        StoreName.TARGET: "target.com",
        StoreName.EBAY: "ebay.com",
        StoreName.IKEA: "ikea.com",
    }

    STORE_LABELS = {
        StoreName.AMAZON: "Amazon",
        StoreName.TARGET: "Target",
        StoreName.EBAY: "eBay",
        StoreName.IKEA: "IKEA",
    }

    STOP_WORDS = {
        "a", "an", "and", "are", "best", "buy", "find", "for", "from",
        "get", "i", "in", "less", "looking", "max", "me", "of", "or",
        "show", "than", "the", "to", "under", "with",
    }

    def __init__(self):
        self.api_key = settings.serp_api_key

    async def search_products(
        self,
        description: str,
        stores: List[StoreName],
        limit_per_store: int,
    ) -> Tuple[List[ProductResult], List[str]]:
        """
        Search each requested store and return ranked, normalized product results.
        """
        if not self.api_key:
            raise ValueError("SERP_API_KEY is not configured")

        intent = parse_search_intent(description)
        search_descriptions = self._build_search_attempts(description, intent)
        fetch_limit = self._build_fetch_limit(limit_per_store)

        accepted_results: List[ProductResult] = []
        errors: List[str] = []
        seen_links = set()
        seen_title_keys = set()

        async with httpx.AsyncClient(timeout=15.0) as client:
            for search_description in search_descriptions:
                tasks = [
                    self._search_store(
                        client=client,
                        description=search_description,
                        store=store,
                        limit_per_store=fetch_limit,
                        max_price=intent.max_price,
                        important_terms=intent.important_terms,
                    )
                    for store in stores
                ]
                store_results = await asyncio.gather(*tasks)

                for store, found, error in store_results:
                    if error:
                        errors.append(f"{store.value}: {error}")
                        continue

                    for product in found:
                        title_key = self._build_title_key(product.title)
                        if product.link in seen_links or title_key in seen_title_keys:
                            continue

                        decision = validate_product(intent, product)
                        if not decision.accepted:
                            continue

                        product.score = round(max(product.score + decision.score_adjustment, 0), 3)
                        accepted_results.append(product)
                        seen_links.add(product.link)
                        seen_title_keys.add(title_key)

                if len(accepted_results) >= self.TARGET_VALID_RESULTS:
                    break

        accepted_results.sort(key=lambda item: item.score, reverse=True)
        return accepted_results, errors

    def _build_search_attempts(self, description: str, intent) -> List[str]:
        attempts = [description]
        broadened_query = build_broadened_query(intent)

        if broadened_query != description and broadened_query not in attempts:
            attempts.append(broadened_query)

        return attempts[:self.MAX_SEARCH_ATTEMPTS]

    def _build_fetch_limit(self, limit_per_store: int) -> int:
        return min(
            max(limit_per_store * self.OVERFETCH_MULTIPLIER, self.TARGET_VALID_RESULTS),
            self.MAX_FETCH_LIMIT,
        )

    def _build_title_key(self, title: str) -> str:
        return " ".join(re.findall(r"[a-z0-9]+", title.lower()))

    async def _search_store(
        self,
        client: httpx.AsyncClient,
        description: str,
        store: StoreName,
        limit_per_store: int,
        max_price: Optional[float],
        important_terms: List[str],
    ) -> Tuple[StoreName, List[ProductResult], Optional[str]]:
        params = self._build_search_params(description, store, limit_per_store)

        try:
            response = await client.get(self.SERPAPI_URL, params=params)
            response.raise_for_status()
            payload = response.json()

            if payload.get("error"):
                return store, [], str(payload["error"])

            products = self._normalize_results(
                payload=payload,
                store=store,
                max_price=max_price,
                important_terms=important_terms,
            )

            return store, products[:limit_per_store], None
        except httpx.HTTPStatusError as exc:
            return store, [], f"SerpApi returned HTTP {exc.response.status_code}"
        except httpx.HTTPError as exc:
            return store, [], str(exc)
        except Exception as exc:
            return store, [], str(exc)

    def _build_store_query(self, description: str, store: StoreName) -> str:
        domain = self.STORE_DOMAINS[store]
        return f"site:{domain} {description}"

    def _build_search_params(
        self,
        description: str,
        store: StoreName,
        limit_per_store: int,
    ) -> Dict[str, Any]:
        base_params: Dict[str, Any] = {
            "api_key": self.api_key,
            "gl": "us",
            "hl": "en",
        }

        if store == StoreName.AMAZON:
            return {
                **base_params,
                "engine": "amazon",
                "k": description,
                "amazon_domain": "amazon.com",
            }

        if store == StoreName.EBAY:
            return {
                **base_params,
                "engine": "ebay",
                "_nkw": description,
                "ebay_domain": "ebay.com",
                "_ipg": 25,
            }

        if store == StoreName.TARGET:
            return {
                **base_params,
                "engine": "google",
                "q": self._build_store_query(description, store),
                "num": max(limit_per_store * 2, 10),
            }

        # SerpApi does not currently provide native IKEA search engines.
        # Google Shopping provides stronger price/rating/image fields than organic search.
        return {
            **base_params,
            "engine": "google_shopping",
            "q": f"{self.STORE_LABELS[store]} {description}",
            "num": max(limit_per_store * 2, 10),
        }

    def _normalize_results(
        self,
        payload: Dict[str, Any],
        store: StoreName,
        max_price: Optional[float],
        important_terms: List[str],
    ) -> List[ProductResult]:
        raw_results = self._get_raw_results(payload, store)

        products: List[ProductResult] = []
        seen_links = set()

        for raw in raw_results:
            title = raw.get("title") or raw.get("name")
            link = self._extract_result_link(raw, store)

            if not title or not link:
                continue
            link = self._canonicalize_store_link(link, store)
            if link in seen_links:
                continue
            if not self._matches_store(raw, link, store):
                continue

            price = self._extract_result_price(raw)
            if max_price is not None and price is not None and price > max_price:
                continue

            image = self._extract_result_image(raw)
            detected_extensions = self._extract_detected_extensions(raw)
            rating = self._parse_float(raw.get("rating") or detected_extensions.get("rating"))
            reviews = self._parse_int(raw.get("reviews") or detected_extensions.get("reviews"))
            snippet = self._extract_result_description(raw)
            score = self._score_result(
                title=title,
                snippet=snippet,
                link=link,
                price=price,
                max_price=max_price,
                important_terms=important_terms,
            )

            products.append(
                ProductResult(
                    store=store,
                    title=title,
                    link=link,
                    description=snippet or None,
                    price=price,
                    image=image,
                    rating=rating,
                    reviews=reviews,
                    source=f"serpapi:{self._engine_for_store(store)}",
                    score=round(score, 3),
                )
            )
            seen_links.add(link)

        products.sort(key=lambda item: item.score, reverse=True)
        return products

    def _get_raw_results(
        self,
        payload: Dict[str, Any],
        store: StoreName,
    ) -> List[Dict[str, Any]]:
        if store == StoreName.AMAZON:
            return payload.get("organic_results") or []
        if store == StoreName.EBAY:
            return payload.get("organic_results") or []
        if store == StoreName.TARGET:
            return payload.get("organic_results") or []
        return payload.get("shopping_results") or []

    def _engine_for_store(self, store: StoreName) -> str:
        if store == StoreName.AMAZON:
            return "amazon"
        if store == StoreName.EBAY:
            return "ebay"
        if store == StoreName.TARGET:
            return "google"
        return "google_shopping"

    def _extract_result_link(self, raw: Dict[str, Any], store: StoreName) -> Optional[str]:
        if store == StoreName.AMAZON:
            return raw.get("link_clean") or raw.get("link")
        return raw.get("link") or raw.get("product_link")

    def _extract_result_image(self, raw: Dict[str, Any]) -> Optional[str]:
        if raw.get("serpapi_thumbnail"):
            return raw["serpapi_thumbnail"]
        if raw.get("thumbnail"):
            return raw["thumbnail"]
        if raw.get("image"):
            return raw["image"]

        thumbnails = raw.get("thumbnails")
        if isinstance(thumbnails, list) and thumbnails:
            first_group = thumbnails[0]
            if isinstance(first_group, list) and first_group:
                return first_group[-1]
            if isinstance(first_group, str):
                return first_group

        return None

    def _extract_result_description(self, raw: Dict[str, Any]) -> str:
        for field in ("snippet", "description", "stock"):
            if raw.get(field):
                return str(raw[field])

        details = []
        brand = raw.get("brand")
        if isinstance(brand, dict):
            brand = brand.get("name")
        if brand:
            details.append(f"Brand: {brand}")
        if raw.get("model_number"):
            details.append(f"Model: {raw['model_number']}")

        return " | ".join(details)

    def _score_result(
        self,
        title: str,
        snippet: str,
        link: str,
        price: Optional[float],
        max_price: Optional[float],
        important_terms: List[str],
    ) -> float:
        haystack = f"{title} {snippet}".lower()
        score = 0.25

        if important_terms:
            matched_terms = sum(1 for term in important_terms if term in haystack)
            score += 0.5 * (matched_terms / len(important_terms))

        if self._looks_like_product_page(link):
            score += 0.15

        if max_price is not None and price is not None:
            score += 0.1 if price <= max_price else -0.3
        elif price is not None:
            score += 0.05

        return max(score, 0)

    def _extract_important_terms(self, description: str) -> List[str]:
        terms = re.findall(r"[a-zA-Z][a-zA-Z0-9-]+", description.lower())
        return [
            term
            for term in terms
            if term not in self.STOP_WORDS and not term.startswith("$")
        ]

    def _extract_max_price(self, description: str) -> Optional[float]:
        patterns = [
            r"(?:under|below|less than|max|maximum|up to)\s*\$?\s*(\d+(?:\.\d{1,2})?)",
            r"\$?\s*(\d+(?:\.\d{1,2})?)\s*(?:or less|and under)",
        ]
        for pattern in patterns:
            match = re.search(pattern, description, flags=re.IGNORECASE)
            if match:
                return self._parse_float(match.group(1))
        return None

    def _extract_result_price(self, raw: Dict[str, Any]) -> Optional[float]:
        price_fields = [
            raw.get("extracted_price"),
            raw.get("price"),
            raw.get("snippet"),
            raw.get("description"),
        ]

        detected_extensions = self._extract_detected_extensions(raw)
        price_fields.extend(
            [
                detected_extensions.get("price"),
                detected_extensions.get("price_from"),
                detected_extensions.get("price_to"),
            ]
        )

        for value in price_fields:
            price = self._parse_price(value)
            if price is not None:
                return price
        return None

    def _extract_detected_extensions(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        rich_snippet = raw.get("rich_snippet") or {}
        detected_extensions: Dict[str, Any] = {}

        for position in ("top", "bottom"):
            position_extensions = rich_snippet.get(position, {}).get("detected_extensions", {})
            if isinstance(position_extensions, dict):
                detected_extensions.update(position_extensions)

        return detected_extensions

    def _parse_price(self, value: Any) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, dict):
            for key in ("extracted", "raw"):
                price = self._parse_price(value.get(key))
                if price is not None:
                    return price
            for key in ("from", "to"):
                price = self._parse_price(value.get(key))
                if price is not None:
                    return price
            return None

        match = re.search(r"\$\s*([0-9][0-9,]*(?:\.\d{1,2})?)", str(value))
        if not match:
            return None
        return self._parse_float(match.group(1).replace(",", ""))

    def _parse_float(self, value: Any) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(str(value).replace(",", ""))
        except (TypeError, ValueError):
            return None

    def _parse_int(self, value: Any) -> Optional[int]:
        if value is None:
            return None
        try:
            return int(float(str(value).replace(",", "")))
        except (TypeError, ValueError):
            return None

    def _matches_store(
        self,
        raw: Dict[str, Any],
        link: str,
        store: StoreName,
    ) -> bool:
        if self._matches_store_domain(link, store):
            return True

        source = str(raw.get("source") or "").lower()
        label = self.STORE_LABELS[store].lower()
        return bool(source and label in source)

    def _matches_store_domain(self, link: str, store: StoreName) -> bool:
        hostname = urlparse(link).hostname or ""
        return self.STORE_DOMAINS[store] in hostname

    def _canonicalize_store_link(self, link: str, store: StoreName) -> str:
        return link

    def _looks_like_product_page(self, link: str) -> bool:
        path = urlparse(link).path.lower()
        product_markers = ["/p/", "/pd/", "/product", "/products/", "/ip/"]
        category_markers = ["/search", "/s/", "/c/", "/cat"]

        if any(marker in path for marker in product_markers):
            return True
        if any(marker in path for marker in category_markers):
            return False
        return bool(path and path != "/")


product_search_service = ProductSearchService()
