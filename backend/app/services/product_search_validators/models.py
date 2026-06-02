"""
Data models for product search validation.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class SearchIntent:
    """
    Structured interpretation of a free-text product search.
    """
    raw_query: str
    normalized_query: str
    terms: List[str] = field(default_factory=list)
    important_terms: List[str] = field(default_factory=list)
    product_phrases: List[str] = field(default_factory=list)
    colors: List[str] = field(default_factory=list)
    max_price: Optional[float] = None
    synonym_groups: Dict[str, List[str]] = field(default_factory=dict)
    excluded_terms: List[str] = field(default_factory=list)
    category: Optional[str] = None


@dataclass(frozen=True)
class ValidationDecision:
    """
    Result of validating a normalized product against a search intent.
    """
    accepted: bool
    score_adjustment: float = 0
    reasons: List[str] = field(default_factory=list)
    matched_terms: List[str] = field(default_factory=list)
    missing_terms: List[str] = field(default_factory=list)
