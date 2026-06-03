"""
Product search service for room upgrade shopping suggestions.
Uses SerpAPI Google Shopping results and normalizes them for the app.
Prioritizes products from preferred stores: Amazon, Target, Walmart, IKEA, eBay.
"""
import asyncio
import re
from urllib.parse import urlparse
from typing import Any, Dict, List, Optional, Set

import httpx

from ..config import get_settings
from ..models.schemas import Product, ProductSearchResult, SelectedProduct, ShoppingListItem

settings = get_settings()

# Priority stores - products from these stores are ranked higher
PREFERRED_STORES = ["Amazon", "Target", "Walmart", "IKEA", "eBay"]

# SerpAPI rate limiting protection
SERPAPI_MAX_CONCURRENCY = 2
SERPAPI_MAX_RETRIES = 3
SERPAPI_BACKOFF_SECONDS = 2.0

# Store name variations for matching
STORE_ALIASES = {
    "amazon": ["amazon", "amazon.com"],
    "target": ["target", "target.com"],
    "walmart": ["walmart", "walmart.com"],
    "ikea": ["ikea", "ikea.com"],
    "ebay": ["ebay", "ebay.com"],
}


class ProductSearchService:
    def __init__(self):
        self.api_key = settings.serp_api_key
        self.base_url = "https://serpapi.com/search.json"
        self._serp_semaphore = asyncio.Semaphore(SERPAPI_MAX_CONCURRENCY)
        # In-memory cache to avoid duplicate API calls within same session
        self._query_cache: Dict[str, List[Product]] = {}

    async def search_products(
        self,
        query: str,
        max_price: Optional[float] = None,
        limit: int = 10,
    ) -> List[Product]:
        if not self.api_key:
            print("SerpAPI key not set")
            return []

        params = {
            "engine": "google_shopping",
            "q": query,
            "api_key": self.api_key,
            "num": limit,
        }

        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.get(self.base_url, params=params)
                response.raise_for_status()
                data = response.json()

                products = []
                for item in data.get("shopping_results", []):
                    product = self._parse_shopping_result(item)
                    if not product:
                        continue
                    if max_price is not None and product.price > max_price:
                        continue
                    products.append(product)
                    if len(products) >= limit:
                        break
        except Exception as exc:
            print(f"SerpAPI product search failed for '{query}': {exc}")
            return []

        return products

    async def search_with_store_preference(
        self,
        base_query: str,
        max_price: Optional[float] = None,
        limit: int = 10,
    ) -> List[Product]:
        """
        Search with preference for specific stores.
        Uses caching to avoid duplicate API calls.
        """
        if not self.api_key:
            print("SerpAPI key not set")
            return []

        # Check cache first
        cache_key = f"{base_query}|{max_price}|{limit}"
        if cache_key in self._query_cache:
            print(f"[Cache HIT] '{base_query[:40]}...'")
            return self._query_cache[cache_key]

        # Single query — store targeting via query text and post-ranking
        products = await self._search_single(base_query, max_price, limit=limit)

        # Sort: preferred stores first, then by rating
        products = self._rank_by_store_preference(products)

        # Cache results
        self._query_cache[cache_key] = products
        return products

    async def _search_single(
        self,
        query: str,
        max_price: Optional[float] = None,
        limit: int = 10,
    ) -> List[Product]:
        """Single search without client reuse (for parallel execution)."""
        params = {
            "engine": "google_shopping",
            "q": query,
            "api_key": self.api_key,
            "num": limit,
        }

        async with self._serp_semaphore:
            try:
                async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                    last_exc: Optional[Exception] = None
                    for attempt in range(SERPAPI_MAX_RETRIES):
                        try:
                            response = await client.get(self.base_url, params=params)
                            if response.status_code == 429:
                                wait_s = SERPAPI_BACKOFF_SECONDS * (attempt + 1)
                                print(
                                    f"SerpAPI rate limited (429) for '{query}'. "
                                    f"Retrying in {wait_s:.1f}s..."
                                )
                                await asyncio.sleep(wait_s)
                                continue
                            response.raise_for_status()
                            data = response.json()

                            products = []
                            for item in data.get("shopping_results", []):
                                product = self._parse_shopping_result(item)
                                if not product:
                                    continue
                                if max_price is not None and product.price > max_price:
                                    continue
                                products.append(product)
                                if len(products) >= limit:
                                    break
                            return products
                        except Exception as exc:
                            last_exc = exc
                            # small backoff between non-429 transient failures
                            await asyncio.sleep(0.5 * (attempt + 1))
                            continue
                    if last_exc:
                        raise last_exc
                    return []
            except Exception as exc:
                print(f"SerpAPI search failed for '{query}': {exc}")
                return []

    def _normalize_title(self, title: str) -> str:
        """Normalize title for deduplication."""
        return re.sub(r"[^a-z0-9]", "", title.lower())[:50]

    def _rank_by_store_preference(self, products: List[Product]) -> List[Product]:
        """Sort products with preferred stores first, then by rating."""
        def sort_key(product: Product):
            store_lower = product.store.lower()
            store_rank = 99  # Default for non-preferred stores

            for idx, preferred in enumerate(PREFERRED_STORES):
                aliases = STORE_ALIASES.get(preferred.lower(), [preferred.lower()])
                if any(alias in store_lower for alias in aliases):
                    store_rank = idx
                    break

            # Secondary sort by rating (higher is better, None treated as 0)
            rating = product.rating if product.rating is not None else 0.0
            return (store_rank, -rating)

        return sorted(products, key=sort_key)

    def _is_preferred_store(self, store_name: str) -> bool:
        """Check if a store is in the preferred list."""
        store_lower = store_name.lower()
        for preferred in PREFERRED_STORES:
            aliases = STORE_ALIASES.get(preferred.lower(), [preferred.lower()])
            if any(alias in store_lower for alias in aliases):
                return True
        return False

    async def search_with_fallback(self, item: ShoppingListItem) -> ProductSearchResult:
        """
        Search for products with single fallback to minimize API calls.
        Target: 1-2 SerpAPI calls per item max.
        """
        # Primary search (1 API call)
        products = await self.search_with_store_preference(
            item.search_description,
            max_price=item.budget_allocation * 1.5,
            limit=6,  # Reduced from 15 to minimize data
        )

        # Single fallback with simpler query (1 API call if needed)
        if not products:
            simple_query = f"{item.item_name}"
            products = await self.search_with_store_preference(
                simple_query,
                max_price=item.budget_allocation * 2,
                limit=6,
            )

        return ProductSearchResult(
            shopping_list_item=item,
            all_candidates=products,
        )

    def _parse_shopping_result(
        self,
        item: Dict[str, Any],
    ) -> Optional[Product]:
        title = str(item.get("title") or "").strip()
        price = self._extract_price(item)
        image_url = (
            item.get("thumbnail")
            or item.get("serpapi_thumbnail")
            or item.get("image")
            or ""
        )
        buy_link = self._resolve_buy_link_sync(item)

        if not title or price is None or not image_url or not buy_link:
            return None

        source = str(item.get("source") or item.get("seller") or "store").strip()

        # Extract enhanced fields
        extensions = item.get("extensions") or []
        snippet = item.get("snippet") or item.get("description") or ""

        # Build detailed description from extensions and snippet
        detailed_desc = self._build_detailed_description(title, extensions, snippet)

        # Extract dimensions, material, color from extensions and title
        dimensions = self._extract_dimensions(extensions, title)
        material = self._extract_material(extensions, title)
        color = self._extract_color(extensions, title)
        brand = self._extract_brand(extensions, title, source)

        # Get high-res image if available
        high_res_image = item.get("image") or item.get("original_image") or image_url

        return Product(
            title=title,
            price=price,
            currency=self._extract_currency(item),
            image_url=image_url,
            buy_link=buy_link,
            store=source,
            rating=self._safe_float(item.get("rating")),
            review_count=self._extract_review_count(item),
            description=snippet or None,
            detailed_description=detailed_desc,
            dimensions=dimensions,
            material=material,
            color=color,
            brand=brand,
            high_res_image_url=high_res_image if high_res_image != image_url else None,
            serpapi_immersive_product_api=item.get("serpapi_immersive_product_api"),
        )

    async def resolve_selected_product_links(
        self,
        selected_products: List[SelectedProduct],
    ) -> List[SelectedProduct]:
        """
        Resolve direct merchant links only for final selected products.

        This keeps search cheap while avoiding broken Google Shopping URLs in the UI.
        Worst case: one extra SerpAPI detail call per selected product.
        """
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            tasks = [
                self._resolve_selected_product_link(selected, client)
                for selected in selected_products
            ]
            await asyncio.gather(*tasks)
        return selected_products

    async def _resolve_selected_product_link(
        self,
        selected: SelectedProduct,
        client: httpx.AsyncClient,
    ) -> None:
        product = selected.chosen_product
        if product.buy_link and not self._is_google_link(product.buy_link):
            return

        immersive_api = product.serpapi_immersive_product_api
        if not immersive_api:
            print(f"No SerpAPI detail URL for selected product: {product.title}")
            return

        direct_link = await self._fetch_immersive_store_link(
            immersive_api=immersive_api,
            preferred_source=product.store,
            client=client,
        )
        if direct_link:
            product.buy_link = direct_link

    def _build_detailed_description(
        self, title: str, extensions: List[str], snippet: str
    ) -> Optional[str]:
        """Build a detailed description from available data."""
        parts = []

        if snippet:
            parts.append(snippet)

        # Add relevant extensions (skip pricing/shipping info)
        skip_patterns = ["free", "shipping", "delivery", "$", "sale", "off"]
        for ext in extensions:
            ext_lower = ext.lower()
            if not any(pat in ext_lower for pat in skip_patterns):
                parts.append(ext)

        if not parts:
            return None

        return " | ".join(parts)

    def _extract_dimensions(
        self, extensions: List[str], title: str
    ) -> Optional[str]:
        """Extract dimensions from extensions or title."""
        # Look for dimension patterns like "40 inch", "5x7", "12\" x 39\""
        patterns = [
            r'(\d+(?:\.\d+)?)\s*(?:x|by)\s*(\d+(?:\.\d+)?)\s*(?:x|by)?\s*(\d+(?:\.\d+)?)?\s*(?:in(?:ch(?:es)?)?|ft|cm|mm|")?',
            r'(\d+(?:\.\d+)?)\s*(?:in(?:ch(?:es)?)?|ft|cm|mm|")',
            r'(\d+)\s*[\'\"]\s*(?:x\s*)?(\d+)\s*[\'\""]?',
        ]

        search_text = " ".join(extensions) + " " + title

        for pattern in patterns:
            match = re.search(pattern, search_text, re.IGNORECASE)
            if match:
                return match.group(0).strip()

        return None

    def _extract_material(
        self, extensions: List[str], title: str
    ) -> Optional[str]:
        """Extract material from extensions or title."""
        materials = [
            "wood", "wooden", "metal", "steel", "iron", "aluminum",
            "plastic", "resin", "wicker", "rattan", "bamboo", "teak",
            "ceramic", "glass", "fabric", "cotton", "polyester", "leather",
            "concrete", "stone", "marble", "granite", "acacia",
        ]

        search_text = (" ".join(extensions) + " " + title).lower()

        found = []
        for material in materials:
            if material in search_text:
                found.append(material.title())

        return ", ".join(found) if found else None

    def _extract_color(
        self, extensions: List[str], title: str
    ) -> Optional[str]:
        """Extract color from extensions or title."""
        colors = [
            "black", "white", "gray", "grey", "brown", "beige", "tan",
            "red", "blue", "green", "yellow", "orange", "purple", "pink",
            "gold", "silver", "bronze", "natural", "teak", "walnut",
            "espresso", "oak", "mahogany", "navy", "cream", "ivory",
        ]

        search_text = (" ".join(extensions) + " " + title).lower()

        found = []
        for color in colors:
            if color in search_text:
                found.append(color.title())

        return ", ".join(found[:2]) if found else None

    def _extract_brand(
        self, extensions: List[str], title: str, store: str
    ) -> Optional[str]:
        """Extract brand from extensions or title."""
        # Check extensions first (often has brand info)
        for ext in extensions:
            # Brand extensions often don't contain numbers
            if ext and not re.search(r'\d', ext) and len(ext) < 30:
                return ext

        # Try to extract from title (usually first word/phrase)
        title_parts = title.split()
        if title_parts:
            first_part = title_parts[0]
            if len(first_part) > 2 and first_part[0].isupper():
                return first_part

        return None

    def _resolve_buy_link_sync(self, item: Dict[str, Any]) -> str:
        """
        Resolve buy link WITHOUT making additional API calls.
        Prioritizes direct merchant links, falls back to Google Shopping link.
        
        This saves ~3-5 API calls per search by skipping the immersive product API.
        """
        # 1. Direct merchant link (best)
        direct_link = item.get("link")
        if direct_link and not self._is_google_link(direct_link):
            return direct_link

        # 2. Product link field
        product_link = item.get("product_link") or ""
        if product_link and not self._is_google_link(product_link):
            return product_link

        # 3. Accept Google Shopping link as fallback (still redirects to store)
        # This saves API calls while still providing a working buy path
        if direct_link:
            return direct_link
        if product_link:
            return product_link

        return ""

    async def _fetch_immersive_store_link(
        self,
        immersive_api: str,
        preferred_source: Optional[str],
        client: httpx.AsyncClient,
    ) -> str:
        try:
            separator = "&" if "?" in immersive_api else "?"
            url = immersive_api
            if "api_key=" not in immersive_api:
                url = f"{immersive_api}{separator}api_key={self.api_key}"
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            print(f"SerpAPI selected product detail lookup failed: {exc}")
            return ""

        product_results = data.get("product_results") or {}
        stores = product_results.get("stores") or []
        if not stores:
            return ""

        preferred_source_lower = str(preferred_source or "").lower()
        preferred_store = None
        if preferred_source_lower:
            preferred_store = next(
                (
                    store
                    for store in stores
                    if preferred_source_lower in str(store.get("name") or "").lower()
                ),
                None,
            )

        store = preferred_store or stores[0]
        link = store.get("link") or ""
        return link if link and not self._is_google_link(link) else ""

    def _is_google_link(self, url: str) -> bool:
        hostname = urlparse(url).netloc.lower()
        return hostname.endswith("google.com") or hostname.endswith("googleadservices.com")

    def _extract_price(self, item: Dict[str, Any]) -> Optional[float]:
        numeric_price = self._safe_float(item.get("extracted_price"))
        if numeric_price is not None:
            return numeric_price

        price_text = str(item.get("price") or "").replace(",", "")
        match = re.search(r"(\d+(?:\.\d{1,2})?)", price_text)
        if not match:
            return None
        return float(match.group(1))

    def _extract_currency(self, item: Dict[str, Any]) -> str:
        price_text = str(item.get("price") or "")
        if "$" in price_text:
            return "USD"
        if "€" in price_text:
            return "EUR"
        if "£" in price_text:
            return "GBP"
        return "USD"

    def _extract_review_count(self, item: Dict[str, Any]) -> Optional[int]:
        reviews = item.get("reviews") or item.get("review_count")
        if isinstance(reviews, int):
            return reviews
        if not reviews:
            return None
        match = re.search(r"(\d[\d,]*)", str(reviews))
        if not match:
            return None
        return int(match.group(1).replace(",", ""))

    def _safe_float(self, value: Any) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None


product_search_service = ProductSearchService()
