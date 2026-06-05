"""
Plant specification service.

Generates a professional plant specification using PLANT_BRIEF_PROMPT and a populated
site palette derived from location intelligence.
"""

from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI

from ..config import get_settings
from ..data.scenario_chunks import PLANT_BRIEF_PROMPT
from ..data.chunk_index import get_plant_constraints, get_budget_key
from ..utils.dimensions import format_area, format_yard_dimensions

settings = get_settings()


class PlantSpecService:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.gpt_model

    async def generate_plant_spec(
        self,
        *,
        site_palette: str,
        user_inputs: Dict[str, Any],
        location_profile: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Generate the professional plant specification text.
        Returns the raw spec string.
        """
        budget = user_inputs.get("budget")
        budget_tier = None
        if isinstance(budget, (int, float)) and budget > 0:
            budget_tier = get_budget_key(float(budget))

        constraints = get_plant_constraints(user_inputs)
        constraints_text = ", ".join(constraints) if constraints else "none"

        city = (location_profile or {}).get("city") or user_inputs.get("city") or user_inputs.get("city_or_region") or ""
        country = (location_profile or {}).get("country_or_region") or user_inputs.get("country") or ""

        unit_system = user_inputs.get("unit_system")
        yard_dims = format_yard_dimensions(
            yard_length=user_inputs.get("yard_length"),
            yard_width=user_inputs.get("yard_width"),
            unit_system=unit_system,
        )
        area = format_area(
            area_sqm=user_inputs.get("dimensions_sqm"),
            unit_system=unit_system,
        )
        dimensions_text = (
            yard_dims
            or area
            or str(user_inputs.get("dimensions") or user_inputs.get("dimensions_sqm") or "")
        ).strip()

        prompt = PLANT_BRIEF_PROMPT.format(
            site_palette=site_palette,
            city=city,
            country=country,
            dimensions=dimensions_text,
            orientation=user_inputs.get("orientation") or "",
            surface_type=user_inputs.get("surface_type") or "",
            style=user_inputs.get("style_preference") or user_inputs.get("style") or "",
            primary_purpose=user_inputs.get("primary_purpose") or "",
            who_uses=user_inputs.get("who_uses") or [],
            maintenance=user_inputs.get("maintenance") or "",
            budget_tier=budget_tier or "",
            allergies=user_inputs.get("allergies") or "",
            pets=f"{user_inputs.get('pets') or ''} | precomputed_filters: {constraints_text}",
        )

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "Return only the plant specification text. No JSON. No markdown fences.",
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=1600,
            temperature=0.3,
        )

        return (response.choices[0].message.content or "").strip()


plant_spec_service = PlantSpecService()

