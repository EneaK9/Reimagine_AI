"""
Public validation entry point for normalized product results.
"""
from ...models.schemas import ProductResult
from .models import SearchIntent, ValidationDecision
from .rules import apply_hard_rules
from .scorer import score_product


def validate_product(intent: SearchIntent, product: ProductResult) -> ValidationDecision:
    hard_rule_decision = apply_hard_rules(intent, product)
    if not hard_rule_decision.accepted:
        return hard_rule_decision

    score_adjustment = score_product(intent, product)
    return ValidationDecision(
        accepted=True,
        score_adjustment=score_adjustment,
        reasons=hard_rule_decision.reasons,
        matched_terms=hard_rule_decision.matched_terms,
        missing_terms=hard_rule_decision.missing_terms,
    )
