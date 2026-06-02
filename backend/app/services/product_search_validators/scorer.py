"""
Soft relevance scoring for validated product search results.
"""
from urllib.parse import urlparse

from ...models.schemas import ProductResult
from .models import SearchIntent


def score_product(intent: SearchIntent, product: ProductResult) -> float:
    adjustment = 0.0
    haystack = _product_text(product)

    for phrase in intent.product_phrases:
        if phrase in haystack:
            adjustment += 0.15

    if intent.important_terms:
        matched_terms = [
            term
            for term in intent.important_terms
            if term in haystack
        ]
        adjustment += 0.2 * (len(matched_terms) / len(intent.important_terms))

    if product.price is not None:
        adjustment += 0.05
        if intent.max_price is not None and product.price <= intent.max_price:
            adjustment += 0.1

    if product.image:
        adjustment += 0.05

    if _looks_like_product_page(product.link):
        adjustment += 0.05
    else:
        adjustment -= 0.1

    if len(intent.colors) > 1:
        missing_colors = [color for color in intent.colors if color not in haystack]
        adjustment -= 0.05 * len(missing_colors)

    return adjustment


def _product_text(product: ProductResult) -> str:
    return " ".join(
        part.lower()
        for part in (product.title, product.description)
        if part
    )


def _looks_like_product_page(link: str) -> bool:
    path = urlparse(link).path.lower()
    product_markers = ["/p/", "/pd/", "/product", "/products/", "/ip/", "/itm/"]
    category_markers = ["/search", "/s/", "/c/", "/cat"]

    if any(marker in path for marker in product_markers):
        return True
    if any(marker in path for marker in category_markers):
        return False
    return bool(path and path != "/")
