"""
Hard validation rules for product search results.
"""
from typing import List

from ...models.schemas import ProductResult
from .models import SearchIntent, ValidationDecision


def apply_hard_rules(intent: SearchIntent, product: ProductResult) -> ValidationDecision:
    reasons: List[str] = []
    matched_terms: List[str] = []
    missing_terms: List[str] = []
    haystack = _product_text(product)
    title_text = product.title.lower()

    if intent.max_price is not None and product.price is not None and product.price > intent.max_price:
        return ValidationDecision(
            accepted=False,
            reasons=[f"price {product.price:g} exceeds budget {intent.max_price:g}"],
        )

    for excluded_term in intent.excluded_terms:
        if excluded_term in haystack:
            return ValidationDecision(
                accepted=False,
                reasons=[f"rejected category term '{excluded_term}' for {intent.category or 'intent'}"],
            )

    for group_name, synonyms in intent.synonym_groups.items():
        matched_synonym = next((term for term in synonyms if term in title_text), None)
        if matched_synonym:
            matched_terms.append(matched_synonym)
            reasons.append(f"matched {group_name} synonym '{matched_synonym}'")
            continue

        missing_terms.append(group_name)
        return ValidationDecision(
            accepted=False,
            reasons=[f"missing required {group_name} signal"],
            missing_terms=missing_terms,
        )

    if len(intent.colors) == 1:
        color = intent.colors[0]
        if color not in haystack:
            return ValidationDecision(
                accepted=False,
                reasons=[f"missing required color '{color}'"],
                missing_terms=[color],
            )
        matched_terms.append(color)
        reasons.append(f"matched required color '{color}'")
    elif len(intent.colors) > 1:
        matched_colors = [color for color in intent.colors if color in haystack]
        if matched_colors:
            matched_terms.extend(matched_colors)
            reasons.append(f"matched color(s) {', '.join(matched_colors)}")

    return ValidationDecision(
        accepted=True,
        reasons=reasons,
        matched_terms=matched_terms,
        missing_terms=missing_terms,
    )


def _product_text(product: ProductResult) -> str:
    return " ".join(
        part.lower()
        for part in (product.title, product.description)
        if part
    )
