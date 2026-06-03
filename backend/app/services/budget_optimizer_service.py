"""
Budget optimizer for selecting a product combination under the user's budget.
Prioritizes MAXIMIZING budget utilization (85%+ target) while getting quality items.
"""
import json
from typing import Any, Dict, List, Tuple

from openai import AsyncOpenAI

from ..config import get_settings
from ..models.schemas import ProductSearchResult, SelectedProduct

settings = get_settings()

# Target utilization: spend as close to the budget as possible without going over.
MIN_BUDGET_UTILIZATION = 0.95
MAX_CANDIDATES_PER_ITEM = 10


class BudgetOptimizerService:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.gpt_model

    async def optimize(
        self,
        search_results: List[ProductSearchResult],
        budget: float,
    ) -> Tuple[List[SelectedProduct], float, bool]:
        usable_results = [
            result for result in search_results if result.all_candidates
        ]
        if not usable_results:
            return [], 0.0, True

        try:
            selections = await self._ask_model(usable_results, budget)
            selected_products = self._map_selections(usable_results, selections)
        except Exception as exc:
            print(f"Budget optimizer AI selection failed, using fallback: {exc}")
            selected_products = self._fallback_selection(usable_results, budget)

        total = sum(item.chosen_product.price for item in selected_products)

        # Post-optimization: upgrade selections if budget utilization is too low
        if total / budget < MIN_BUDGET_UTILIZATION:
            selected_products = self._upgrade_selections(
                selected_products, usable_results, budget
            )
            total = sum(item.chosen_product.price for item in selected_products)

        return selected_products, total, total <= budget

    async def _ask_model(
        self,
        search_results: List[ProductSearchResult],
        budget: float,
    ) -> List[Dict[str, Any]]:
        summary = self._build_candidate_summary(search_results)
        min_spend = budget * MIN_BUDGET_UTILIZATION

        response = await self.client.chat.completions.create(
            model=self.model,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a budget shopping assistant that MAXIMIZES value. "
                        "Your goal is to spend as close to the full budget as possible "
                        "while getting quality items. Return only valid JSON."
                    ),
                },
                {
                    "role": "user",
                    "content": f"""Total budget: ${budget:.2f}
Minimum spending target: ${min_spend:.2f} (must spend at least 95% of budget)

{summary}

IMPORTANT RULES:
1. Select ALL items (both must-have AND nice-to-have) if they fit within budget
2. Prefer HIGHER-PRICED options that are still within each item's budget allocation
3. Choose quality items with good ratings - don't just pick the cheapest
4. The total should be as close to ${budget:.2f} as possible (aim for 95-100%)
5. Only skip nice-to-have items if including them would exceed the total budget

Pick one option per item to MAXIMIZE budget utilization while staying under ${budget:.2f}.

Return exactly:
{{
  "selections": [
    {{"item_index": 0, "option_index": 0, "reasoning": "short reason"}}
  ],
  "total_spent": 0.00
}}""",
                },
            ],
            max_tokens=1200,
            temperature=0.3,
        )

        data = self._load_json(response.choices[0].message.content or "{}")
        return data.get("selections", [])

    def _build_candidate_summary(self, search_results: List[ProductSearchResult]) -> str:
        lines = []
        for item_index, result in enumerate(search_results):
            item = result.shopping_list_item
            lines.append(
                f"Item {item_index}: {item.item_name} "
                f"(target ${item.budget_allocation:.2f}, priority {item.priority})"
            )
            for option_index, product in enumerate(result.all_candidates[:MAX_CANDIDATES_PER_ITEM]):
                rating = product.rating if product.rating is not None else "N/A"
                lines.append(
                    f"  Option {option_index}: {product.title} - "
                    f"${product.price:.2f} at {product.store}, rating {rating}"
                )
        return "\n".join(lines)

    def _map_selections(
        self,
        search_results: List[ProductSearchResult],
        selections: List[Dict[str, Any]],
    ) -> List[SelectedProduct]:
        selected = []
        for selection in selections:
            item_index = int(selection.get("item_index", selection.get("itemIndex", -1)))
            option_index = int(selection.get("option_index", selection.get("optionIndex", -1)))
            if item_index < 0 or item_index >= len(search_results):
                continue

            result = search_results[item_index]
            candidates = result.all_candidates
            if option_index < 0 or option_index >= min(len(candidates), MAX_CANDIDATES_PER_ITEM):
                continue

            selected.append(
                SelectedProduct(
                    shopping_list_item=result.shopping_list_item,
                    chosen_product=candidates[option_index],
                    all_candidates=candidates,
                    reasoning=selection.get("reasoning"),
                )
            )

        if selected:
            return selected
        raise ValueError("No valid selections returned")

    def _fallback_selection(
        self,
        search_results: List[ProductSearchResult],
        budget: float,
    ) -> List[SelectedProduct]:
        """
        Fallback selection that MAXIMIZES budget utilization.
        Prefers higher-value options within allocation, not just cheapest.
        """
        selected = []
        total = 0.0

        # Process must-have items first, then nice-to-have
        priority_order = {"must-have": 0, "nice-to-have": 1}
        ordered_results = sorted(
            search_results,
            key=lambda result: priority_order.get(result.shopping_list_item.priority, 0),
        )

        for result in ordered_results:
            allocation = result.shopping_list_item.budget_allocation
            candidates = result.all_candidates[:10]

            # Sort by price DESCENDING to prefer higher-value options
            candidates_by_price = sorted(candidates, key=lambda p: -p.price)

            # Find the best product that fits: highest price within allocation that doesn't bust budget
            choice = None
            for product in candidates_by_price:
                # Allow up to 20% over allocation if total budget permits
                max_price = min(allocation * 1.2, budget - total)
                if product.price <= max_price:
                    choice = product
                    break

            # If no product fits within allocation, find any that fits in remaining budget
            if not choice:
                affordable = [p for p in candidates if total + p.price <= budget]
                if affordable:
                    # Pick the highest-priced affordable option
                    choice = max(affordable, key=lambda p: p.price)

            if not choice:
                # Skip if nothing fits
                if result.shopping_list_item.priority == "nice-to-have":
                    continue
                # For must-have, take cheapest even if over budget
                choice = min(candidates, key=lambda p: p.price) if candidates else None

            if choice:
                selected.append(
                    SelectedProduct(
                        shopping_list_item=result.shopping_list_item,
                        chosen_product=choice,
                        all_candidates=result.all_candidates,
                        reasoning="Selected as best value within budget allocation.",
                    )
                )
                total += choice.price

        return selected

    def _upgrade_selections(
        self,
        selected: List[SelectedProduct],
        all_results: List[ProductSearchResult],
        budget: float,
    ) -> List[SelectedProduct]:
        """
        Upgrade selections to higher-priced options if budget utilization is too low.
        Also adds any missing nice-to-have items if budget permits.
        """
        current_total = sum(item.chosen_product.price for item in selected)
        remaining = budget - current_total

        # Build a map of item names already selected
        selected_items = {s.shopping_list_item.item_name for s in selected}

        # First: add any missing items that fit in remaining budget
        for result in all_results:
            if result.shopping_list_item.item_name in selected_items:
                continue

            candidates = result.all_candidates[:10]
            affordable = [p for p in candidates if p.price <= remaining]
            if affordable:
                # Pick the highest-priced affordable option
                choice = max(affordable, key=lambda p: p.price)
                selected.append(
                    SelectedProduct(
                        shopping_list_item=result.shopping_list_item,
                        chosen_product=choice,
                        all_candidates=result.all_candidates,
                        reasoning="Added to maximize budget utilization.",
                    )
                )
                remaining -= choice.price

        # Second: upgrade existing selections to higher-priced alternatives
        for i, item in enumerate(selected):
            current_price = item.chosen_product.price
            candidates = item.all_candidates[:10]

            # Find upgrades: higher price but still fits in remaining budget
            upgrades = [
                p for p in candidates
                if p.price > current_price and (p.price - current_price) <= remaining
            ]

            if upgrades:
                # Pick the highest upgrade that fits
                upgrade = max(upgrades, key=lambda p: p.price)
                price_diff = upgrade.price - current_price

                selected[i] = SelectedProduct(
                    shopping_list_item=item.shopping_list_item,
                    chosen_product=upgrade,
                    all_candidates=item.all_candidates,
                    reasoning=f"Upgraded from ${current_price:.2f} to maximize budget.",
                )
                remaining -= price_diff

        return selected

    def _load_json(self, text: str) -> Dict[str, Any]:
        cleaned = text.replace("```json", "").replace("```", "").strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start >= 0 and end > start:
                return json.loads(cleaned[start : end + 1])
            raise


budget_optimizer_service = BudgetOptimizerService()
