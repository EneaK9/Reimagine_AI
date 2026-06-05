"""
Scene analysis service for budget room upgrades.
Uses OpenAI vision to turn a room/yard photo into a small shopping plan.
"""
import json
import re
from typing import Any, Dict, Optional

from openai import AsyncOpenAI

from ..config import get_settings
from ..models.schemas import SceneAnalysis, ShoppingListItem

settings = get_settings()

MAX_SHOPPING_LIST_ITEMS = 8


class SceneAnalysisService:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.gpt_model

    async def analyze_scene(
        self,
        image_base64: str,
        prompt: str,
        budget: float,
        currency: str = "USD",
    ) -> SceneAnalysis:
        image_base64 = self._strip_data_url(image_base64)
        user_prompt = self._build_prompt(prompt, budget, currency)

        response = await self.client.chat.completions.create(
            model=self.model,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an interior and exterior design assistant. "
                        "Analyze rooms, yards, patios, and living spaces. "
                        "Return only valid JSON matching the requested schema."
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_base64}"
                            },
                        },
                    ],
                },
            ],
            max_tokens=1200,
            temperature=0.4,
        )

        text = response.choices[0].message.content or "{}"
        return self._parse_scene_analysis(text, budget)

    async def infer_budget(
        self,
        image_base64: str,
        prompt: str,
        currency: str = "USD",
    ) -> float:
        """
        Infer a practical shopping budget when the user does not provide one.
        Uses a cheap regex first, then asks the LLM, then falls back to heuristics.
        """
        explicit_budget = self.parse_budget(prompt)
        if explicit_budget is not None and explicit_budget > 0:
            return explicit_budget

        image_base64 = self._strip_data_url(image_base64)
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You estimate realistic shopping budgets for room and yard "
                            "makeovers. Return only valid JSON."
                        ),
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": f"""User request: "{prompt}"

Look at the photo and infer a practical product-shopping budget in {currency}.
Estimate only removable purchasable products such as furniture, lights, decor, planters, rugs, pillows, and accessories.
Do NOT include construction costs such as flooring, tiles, concrete, landscaping, decks, pergolas, roofs, walls, or permanent hardscape.

Return exactly:
{{
  "budget": 300,
  "reasoning": "short explanation"
}}

Rules:
- If the user implies a small refresh, use 150-300.
- If the user implies a medium room/yard upgrade, use 300-600.
- If the user mentions family hosting, kids, pets, gatherings, or summer evenings, use 600-900.
- Use a round number ending in 0 or 50.
- Return only JSON.""",
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_base64}"
                                },
                            },
                        ],
                    },
                ],
                max_tokens=200,
                temperature=0.2,
            )
            data = self._load_json(response.choices[0].message.content or "{}")
            budget = float(data.get("budget") or 0)
            if budget > 0:
                return budget
        except Exception as exc:
            print(f"Budget inference failed, using heuristic fallback: {exc}")

        return self._fallback_budget(prompt)

    def parse_budget(self, prompt: str) -> Optional[float]:
        dollar_match = re.search(r"\$\s*(\d+(?:\.\d{1,2})?)", prompt)
        if dollar_match:
            return float(dollar_match.group(1))

        trailing_dollar_match = re.search(r"(\d+(?:\.\d{1,2})?)\s*\$", prompt)
        if trailing_dollar_match:
            return float(trailing_dollar_match.group(1))

        word_match = re.search(
            r"(\d+(?:\.\d{1,2})?)\s*(dollars|bucks|usd)",
            prompt,
            flags=re.IGNORECASE,
        )
        if word_match:
            return float(word_match.group(1))

        return None

    def _fallback_budget(self, prompt: str) -> float:
        prompt_lower = prompt.lower()
        if any(
            token in prompt_lower
            for token in ["family", "kids", "dog", "friends", "hosting", "hangout"]
        ):
            return 700.0
        if any(token in prompt_lower for token in ["yard", "lawn", "patio", "outdoor"]):
            return 500.0
        if any(token in prompt_lower for token in ["cheap", "low budget", "simple"]):
            return 200.0
        return 300.0

    def _build_prompt(self, prompt: str, budget: float, currency: str) -> str:
        # Start with a realistic per-item target, but allow the model to vary
        # allocations so large budgets can become complete shopping lists.
        target_per_item = budget / 6

        return f"""The user says: "{prompt}"
Their total budget is {currency} {budget:.2f}.

GOAL: Help them spend most of their budget (at least 85%) on impactful products.

Analyze this photo and return a JSON object with this exact structure:
{{
  "space_type": "small backyard lawn, paved patio, living room, bedroom, etc.",
  "existing_items": ["array of strings describing visible existing items, including ground surfaces like grass, pavers, concrete, tile, deck, or gravel"],
  "style_observation": "one sentence about the current style or vibe",
  "shopping_list": [
    {{
      "item_name": "short product category name (e.g., outdoor bench, string lights)",
      "search_description": "DETAILED search query - see format below",
      "budget_allocation": {target_per_item:.0f},
      "placement": "SPECIFIC placement instruction for image generation",
      "priority": "must-have"
    }}
  ]
}}

SEARCH DESCRIPTION FORMAT (be specific for better product matches):
- Include SIZE/DIMENSIONS: "40 inch", "5x7 feet", "large", "compact"
- Include MATERIAL: "wood", "metal", "wicker", "ceramic", "LED"
- Include COLOR (if relevant): "natural wood", "black metal", "warm white"
- Include PRICE RANGE: "under $100", "around $50"
- Include STORE HINTS: "from Amazon", "from Target or Walmart"

GOOD search_description examples:
- "wooden backless garden bench 40 inch, teak or acacia wood, weather resistant, under $80, Amazon or Walmart"
- "outdoor solar string lights 50 feet, warm white LED, waterproof, around $35, Target"
- "large ceramic planter pot 12 inch, colorful pattern, outdoor use, under $40"
- "compact outdoor conversation set 4 piece, wicker with cushions, weather resistant, under $300"

BAD search_description examples (too vague):
- "outdoor bench"
- "lights for garden"
- "planter"

PLACEMENT must be specific for image generation:
- GOOD: "placed on the existing paved border on the left side, without changing the lawn"
- GOOD: "placed directly on the grass near the back-left corner"
- GOOD: "hung only from the existing visible overhead beam or post; do not create a new pergola"
- BAD: "in the garden" (too vague)
- BAD: "centered on the patio" if no patio surface exists in the original photo

RULES:
1. Budget allocations MUST sum to at least {budget * 0.95:.2f} (use 95%+ of budget)
2. Include enough products to create a complete, budget-filling plan: usually 4-8 items, never fewer than 4 unless the budget is extremely small
3. First 2-3 items should be "must-have"; the rest can be "nice-to-have"
4. Allocate MORE budget to impactful items (furniture > decor)
5. Make search descriptions DETAILED for better product matching
6. Do NOT suggest products or placements that require adding/changing flooring, floor tiles, pavers, concrete slabs, decks, pergolas, roofs, walls, landscaping construction, or any permanent hardscape
7. If the original image is mostly grass, keep it grass. Choose products that can sit on grass or existing visible paved borders
8. Return up to {MAX_SHOPPING_LIST_ITEMS} shopping_list items
9. Return only JSON. No markdown, no comments, no backticks."""

    def _parse_scene_analysis(self, text: str, budget: float) -> SceneAnalysis:
        data = self._load_json(text)

        # Detect if the scene has grass/lawn surfaces (rugs are inappropriate there)
        existing_items = data.get("existing_items") or data.get("existingItems") or []
        existing_text = " ".join(str(item).lower() for item in existing_items)
        has_grass = any(kw in existing_text for kw in ["grass", "lawn", "turf", "soil", "dirt", "mud"])

        raw_items = data.get("shopping_list") or data.get("shoppingList") or []
        items = []
        running_total = 0.0
        for raw_item in raw_items[:MAX_SHOPPING_LIST_ITEMS]:
            # Filter out rugs/carpets/mats if scene has grass surfaces
            item_name = (raw_item.get("item_name") or raw_item.get("itemName") or "").lower()
            if has_grass and any(kw in item_name for kw in ["rug", "carpet", "mat", "runner"]):
                continue
            allocation = float(
                raw_item.get("budget_allocation")
                or raw_item.get("budgetAllocation")
                or 0
            )
            if allocation <= 0:
                continue

            # Keep model output honest if allocations drift over budget.
            remaining = max(budget - running_total, 0)
            allocation = min(allocation, remaining)
            if allocation <= 0:
                break

            priority = raw_item.get("priority") or "must-have"
            if priority not in {"must-have", "nice-to-have"}:
                priority = "must-have"

            items.append(
                ShoppingListItem(
                    item_name=raw_item.get("item_name") or raw_item.get("itemName") or "decor item",
                    search_description=raw_item.get("search_description")
                    or raw_item.get("searchDescription")
                    or raw_item.get("item_name")
                    or raw_item.get("itemName")
                    or "home decor",
                    budget_allocation=allocation,
                    placement=raw_item.get("placement") or "placed naturally in the space",
                    priority=priority,
                )
            )
            running_total += allocation

        return SceneAnalysis(
            space_type=data.get("space_type") or data.get("spaceType") or "room",
            existing_items=data.get("existing_items") or data.get("existingItems") or [],
            style_observation=data.get("style_observation")
            or data.get("styleObservation")
            or "The space is ready for a practical upgrade.",
            shopping_list=items,
        )

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

    def _strip_data_url(self, image_base64: str) -> str:
        if "," in image_base64 and image_base64.startswith("data:"):
            return image_base64.split(",", 1)[1]
        return image_base64


scene_analysis_service = SceneAnalysisService()
