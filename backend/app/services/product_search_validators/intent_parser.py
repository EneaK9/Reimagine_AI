"""
Intent parsing for product search validation.
"""
import re
from typing import List, Optional

from .models import SearchIntent


STOP_WORDS = {
    "a", "an", "and", "are", "around", "best", "buy", "find", "for", "from",
    "get", "i", "in", "less", "looking", "max", "me", "of", "or", "show",
    "than", "the", "to", "under", "with",
}

LOW_VALUE_RETRY_TERMS = {
    "around", "outdoor", "outdoors", "indoor", "indoors", "new", "cheap",
}

COLORS = {
    "beige", "black", "blue", "brown", "clear", "cream", "gold", "golden",
    "gray", "green", "grey", "ivory", "orange", "pink", "purple", "red",
    "silver", "tan", "teal", "white", "yellow",
}

PRODUCT_NOUNS = {
    "bag", "backpack", "chair", "desk", "lamp", "mirror", "purse", "rug",
    "sofa", "table", "vase",
}

PHRASE_SYNONYMS = {
    "accent chair": {
        "category": "accent_chair",
        "synonym_groups": {
            "accent": ["accent", "club", "barrel", "armchair", "lounge"],
            "chair": ["chair", "armchair"],
        },
        "excluded_terms": [
            "cover", "cushion", "ottoman only", "pillow", "slipcover", "table",
        ],
    },
    "coffee table": {
        "category": "coffee_table",
        "synonym_groups": {
            "coffee": ["coffee", "cocktail", "center"],
            "table": ["table"],
        },
        "excluded_terms": [
            "candle holder", "coaster", "decorative tray", "serving tray",
            "tray",
        ],
    },
    "floor lamp": {
        "category": "floor_lamp",
        "synonym_groups": {
            "floor": ["floor", "standing", "stand"],
            "lamp": ["lamp", "lighting"],
        },
        "excluded_terms": [
            "bulb only", "lamp shade", "replacement shade", "shade only",
        ],
    },
    "puff bag": {
        "category": "puffer_bag",
        "synonym_groups": {
            "puff": ["puff", "puffer", "puffy", "quilted", "padded"],
            "bag": ["bag", "handbag", "hobo", "purse", "shoulder", "tote", "crossbody"],
        },
        "excluded_terms": [
            "backpack", "bean bag", "beanbag", "book bag", "candy", "chair",
            "couch", "cosmetic", "drawstring", "fat free", "footstool",
            "futon", "gluten free", "gym bag", "lounger", "makeup",
            "organizer", "ottoman", "peppermint", "sackpack", "sofa",
            "toiletry",
        ],
    },
    "puffer bag": {
        "category": "puffer_bag",
        "synonym_groups": {
            "puff": ["puff", "puffer", "puffy", "quilted", "padded"],
            "bag": ["bag", "handbag", "hobo", "purse", "shoulder", "tote", "crossbody"],
        },
        "excluded_terms": [
            "backpack", "bean bag", "beanbag", "book bag", "candy", "chair",
            "couch", "cosmetic", "drawstring", "fat free", "footstool",
            "futon", "gluten free", "gym bag", "lounger", "makeup",
            "organizer", "ottoman", "peppermint", "sackpack", "sofa",
            "toiletry",
        ],
    },
    "wooden coffee table": {
        "category": "coffee_table",
        "synonym_groups": {
            "wood": ["wood", "wooden", "walnut", "oak", "pine"],
            "coffee": ["coffee", "cocktail", "center"],
            "table": ["table"],
        },
        "excluded_terms": [
            "candle holder", "coaster", "decorative tray", "serving tray",
            "tray",
        ],
    },
}


def parse_search_intent(description: str) -> SearchIntent:
    normalized_query = _normalize_text(description)
    terms = _extract_terms(normalized_query)
    important_terms = [term for term in terms if term not in STOP_WORDS and not term.isdigit()]
    product_phrases = _extract_product_phrases(terms, normalized_query)
    colors = [term for term in important_terms if term in COLORS]
    max_price = _extract_max_price(description)

    synonym_groups = {}
    excluded_terms: List[str] = []
    category: Optional[str] = None

    for phrase in product_phrases:
        phrase_config = PHRASE_SYNONYMS.get(phrase)
        if not phrase_config:
            continue

        category = str(phrase_config["category"])
        synonym_groups.update(phrase_config["synonym_groups"])
        excluded_terms.extend(phrase_config["excluded_terms"])

    return SearchIntent(
        raw_query=description,
        normalized_query=normalized_query,
        terms=terms,
        important_terms=important_terms,
        product_phrases=product_phrases,
        colors=colors,
        max_price=max_price,
        synonym_groups=synonym_groups,
        excluded_terms=_dedupe(excluded_terms),
        category=category,
    )


def build_broadened_query(intent: SearchIntent) -> str:
    """
    Build a second-attempt query that keeps product and color intent but removes
    budget language and low-signal descriptors.
    """
    kept_terms = [
        term
        for term in intent.important_terms
        if term not in LOW_VALUE_RETRY_TERMS and term not in {"below", "maximum", "up"}
    ]

    colors = [term for term in kept_terms if term in intent.colors]
    phrase_terms = []
    for phrase in intent.product_phrases:
        phrase_terms.extend(phrase.split())

    ordered_terms = _dedupe(colors + phrase_terms + kept_terms)
    return " ".join(ordered_terms) or intent.raw_query


def _extract_product_phrases(terms: List[str], normalized_query: str) -> List[str]:
    phrases: List[str] = []

    for phrase in PHRASE_SYNONYMS:
        if phrase in normalized_query:
            phrases.append(phrase)

    for index, term in enumerate(terms[:-1]):
        next_term = terms[index + 1]
        if next_term in PRODUCT_NOUNS:
            phrases.append(f"{term} {next_term}")

    return _dedupe(phrases)


def _extract_terms(value: str) -> List[str]:
    return re.findall(r"[a-z][a-z0-9-]+", value)


def _extract_max_price(description: str) -> Optional[float]:
    patterns = [
        r"(?:under|below|less than|max|maximum|up to)\s*(?:around|about)?\s*\$?\s*\d+(?:\.\d{1,2})?\s*[-–]\s*\$?\s*(\d+(?:\.\d{1,2})?)\s*\$?",
        r"\$?\s*\d+(?:\.\d{1,2})?\s*[-–]\s*\$?\s*(\d+(?:\.\d{1,2})?)\s*\$?",
        r"(?:under|below|less than|max|maximum|up to)\s*\$?\s*(\d+(?:\.\d{1,2})?)",
        r"\$?\s*(\d+(?:\.\d{1,2})?)\s*(?:or less|and under)",
    ]
    for pattern in patterns:
        match = re.search(pattern, description, flags=re.IGNORECASE)
        if match:
            return float(match.group(1))
    return None


def _normalize_text(value: str) -> str:
    return " ".join(value.lower().replace("$", " $").split())


def _dedupe(values: List[str]) -> List[str]:
    seen = set()
    deduped = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped
