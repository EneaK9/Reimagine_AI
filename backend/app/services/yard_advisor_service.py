"""
Yard design advisor service.
Generates comprehensive design advice with natural language reasoning
using relevant scenario chunks as context.
"""

import json
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI

from ..config import get_settings
from .scenario_context_service import (
    ScenarioContextService,
    YardInputs,
    scenario_context_service,
)
from ..utils.dimensions import format_area, format_yard_dimensions

settings = get_settings()


ADVISOR_SYSTEM_PROMPT = """You are an expert outdoor space designer helping users transform their yards, patios, and gardens. You provide thoughtful, practical advice based on each user's specific situation.

You have been given design guidelines that apply to this user's circumstances. Use this knowledge to provide advice, but write naturally - as a friendly expert consultant would. Do NOT cite rule numbers or modules. Instead, explain your reasoning in plain language using phrases like:
- "In coastal environments, typically..."
- "With children in the space, it's important to..."
- "For best results in north-facing gardens..."
- "Since you're renting, I'd recommend..."

## DESIGN KNOWLEDGE FOR THIS USER:

{context}

---

## YOUR TASK:

Analyze the user's situation and generate a comprehensive design plan. Your response must be a valid JSON object with this structure:

{{
  "space_assessment": {{
    "summary": "Brief description of the space and situation",
    "size_category": "micro/small/medium/large",
    "key_characteristics": ["list", "of", "notable", "features"]
  }},
  "key_constraints": [
    {{
      "title": "Short constraint name (e.g., 'Coastal Environment')",
      "explanation": "Why this matters, written naturally",
      "impact": "What this means for the design",
      "user_action": "What the user should do or be aware of"
    }}
  ],
  "design_approach": {{
    "strategy": "Overall approach in one sentence",
    "reasoning": "Why this approach works for their situation",
    "focal_point": "The main visual anchor of the design",
    "zones": ["list", "of", "defined", "areas"]
  }},
  "action_plan": [
    {{
      "step": 1,
      "action": "Brief action title",
      "detail": "Specific instructions",
      "reasoning": "Why this step matters"
    }}
  ],
  "product_requirements": [
    {{
      "category": "e.g., seating, planters, lighting",
      "requirements": "Specific requirements based on constraints",
      "search_terms": ["suggested", "search", "keywords"],
      "budget_allocation": 0.0,
      "placement": "Where in the space"
    }}
  ],
  "warnings": [
    {{
      "severity": "critical/important/info",
      "title": "Short warning title",
      "message": "Detailed explanation"
    }}
  ],
  "seasonal_notes": {{
    "spring": "What to do/expect in spring",
    "summer": "What to do/expect in summer",
    "autumn": "What to do/expect in autumn",
    "winter": "What to do/expect in winter"
  }}
}}

Write naturally and helpfully. The user should feel like they're getting advice from a knowledgeable friend, not reading a rulebook."""


LOCATION_ASSESSMENT_REQUIREMENT = """IMPORTANT: The user may provide only a city/location and we may derive the rest.
You MUST include a clear location assessment in the output:
- Add at least one item in space_assessment.key_characteristics that references the derived climate risks (UV/heat/humidity/wind/frost).
- Also include a key_constraint titled \"Location & climate profile\" summarizing the most important derived constraints and what they mean."""


class YardAdvisorService:
    """
    Generates comprehensive design advice using LLM with focused scenario context.
    """
    
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.gpt_model
        self.context_service = scenario_context_service
    
    async def generate_design_advice(
        self,
        inputs: YardInputs,
        photo_analysis: Optional[Dict[str, Any]] = None,
        location_profile: Optional[Dict[str, Any]] = None,
        site_palette: Optional[str] = None,
        override_chunk_ids: Optional[List[str]] = None,
        dynamic_chunks: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Generate comprehensive design advice based on user inputs.
        
        Args:
            inputs: YardInputs with the user's situation
            photo_analysis: Optional analysis from scene analysis service
            
        Returns:
            Structured design advice dictionary
        """
        # Check if we have enough inputs to generate meaningful advice
        if not self.context_service.has_inputs(inputs):
            return self._empty_advice()
        
        # Assemble relevant context (including optional overrides and dynamic chunks)
        context = self.context_service.assemble_context(
            inputs,
            max_tokens=6000,
            extra_chunk_ids=override_chunk_ids,
            dynamic_chunks=dynamic_chunks,
        )
        context_text = self.context_service.format_for_prompt(context)
        
        print(f"[YardAdvisor] Assembled {len(context.chunk_ids)} chunks, ~{context.total_tokens} tokens")
        print(f"[YardAdvisor] Chunks: {context.chunk_ids}")
        
        # Build system prompt with context
        system_prompt = (
            ADVISOR_SYSTEM_PROMPT.format(context=context_text)
            + "\n\n"
            + LOCATION_ASSESSMENT_REQUIREMENT
        )
        
        # Build user prompt
        user_prompt = self._build_user_prompt(
            inputs,
            photo_analysis=photo_analysis,
            location_profile=location_profile,
            site_palette=site_palette,
        )
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=3000,
                temperature=0.3,
            )
            
            advice_text = response.choices[0].message.content or "{}"
            advice = self._parse_advice(advice_text)
            
            # Add metadata
            advice["_metadata"] = {
                "chunks_used": context.chunk_ids,
                "tokens_used": context.total_tokens,
                "inputs_summary": self.context_service.summarize_inputs(inputs),
            }
            
            return advice
            
        except Exception as exc:
            print(f"[YardAdvisor] Error generating advice: {exc}")
            return self._error_advice(str(exc))
    
    def _build_user_prompt(
        self,
        inputs: YardInputs,
        photo_analysis: Optional[Dict[str, Any]] = None,
        location_profile: Optional[Dict[str, Any]] = None,
        site_palette: Optional[str] = None,
    ) -> str:
        """Build the user prompt with all available information."""
        
        parts = ["Please create a design plan for this outdoor space:\n"]
        
        # Add input summary
        parts.append("## USER'S SITUATION:\n")

        yard_dims = format_yard_dimensions(
            yard_length=getattr(inputs, "yard_length", None),
            yard_width=getattr(inputs, "yard_width", None),
            unit_system=getattr(inputs, "unit_system", None),
        )
        area = format_area(
            area_sqm=getattr(inputs, "dimensions_sqm", None),
            unit_system=getattr(inputs, "unit_system", None),
        )

        if yard_dims and area:
            parts.append(f"- Space dimensions: {yard_dims} (approx. {area})")
        elif yard_dims:
            parts.append(f"- Space dimensions: {yard_dims}")
        elif area:
            parts.append(f"- Space size: approximately {area}")
        if inputs.orientation:
            parts.append(f"- Orientation: {inputs.orientation}-facing")
        if inputs.surface_type:
            parts.append(f"- Ground surface: {inputs.surface_type.replace('_', ' ')}")
        if inputs.slope:
            parts.append(f"- Terrain: {inputs.slope.replace('_', ' ')}")
        if inputs.city_or_region:
            parts.append(f"- Location: {inputs.city_or_region}")
        if inputs.environment_type:
            parts.append(f"- Environment: {inputs.environment_type.replace('_', ' ')}")
        if inputs.primary_purpose:
            parts.append(f"- Main use: {inputs.primary_purpose.replace('_', ' ')}")
        if inputs.who_uses:
            parts.append(f"- Who uses it: {', '.join(inputs.who_uses)}")
        if inputs.maintenance:
            parts.append(f"- Maintenance preference: {inputs.maintenance.replace('_', ' ')}")
        if inputs.style_preference:
            parts.append(f"- Style: {inputs.style_preference.replace('_', ' ')}")
        if inputs.ownership:
            parts.append(f"- Ownership: {inputs.ownership}")
        if inputs.budget is not None:
            parts.append(f"- Budget: ${inputs.budget:,.0f}")
        
        # Add photo analysis if available
        if photo_analysis:
            parts.append("\n## FROM PHOTO ANALYSIS:\n")
            if photo_analysis.get("space_type"):
                parts.append(f"- Space type: {photo_analysis['space_type']}")
            if photo_analysis.get("existing_items"):
                items = photo_analysis["existing_items"]
                if items:
                    parts.append(f"- Existing items: {', '.join(items)}")
            if photo_analysis.get("style_observation"):
                parts.append(f"- Current style: {photo_analysis['style_observation']}")

        if location_profile:
            parts.append("\n## LOCATION INTELLIGENCE (DERIVED):\n")
            # Keep this short and high-signal; the full details are in the scenario context chunks.
            for key in [
                "country_or_region",
                "usda_hardiness_zone",
                "annual_rainfall_mm",
                "july_avg_high_c",
                "annual_sunshine_hours",
                "solar_lighting_viability",
                "uv_index_summer",
                "summer_humidity_pct",
                "avg_wind_kmh",
                "prevailing_wind_direction",
                "elevation_m",
                "first_frost_month",
                "irrigation_required",
                "special_flags",
            ]:
                if key in location_profile and location_profile.get(key) not in (None, "", [], {}):
                    parts.append(f"- {key}: {location_profile.get(key)}")

        if site_palette:
            parts.append("\n## SITE PALETTE:\n")
            parts.append(site_palette)
        
        parts.append("\n\nGenerate the complete design plan now as a JSON object.")
        
        return "\n".join(parts)
    
    def _parse_advice(self, text: str) -> Dict[str, Any]:
        """Parse the LLM response into structured advice."""
        try:
            # Clean up potential markdown formatting
            cleaned = text.replace("```json", "").replace("```", "").strip()
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Try to extract JSON from the text
            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end > start:
                try:
                    return json.loads(text[start:end + 1])
                except json.JSONDecodeError:
                    pass
            return self._error_advice("Failed to parse advice response")
    
    def _empty_advice(self) -> Dict[str, Any]:
        """Return empty advice structure when no inputs provided."""
        return {
            "space_assessment": None,
            "key_constraints": [],
            "design_approach": None,
            "action_plan": [],
            "product_requirements": [],
            "warnings": [],
            "seasonal_notes": None,
            "_metadata": {
                "note": "No yard-specific inputs provided. Advice not generated."
            },
        }
    
    def _error_advice(self, error: str) -> Dict[str, Any]:
        """Return error advice structure."""
        return {
            "space_assessment": None,
            "key_constraints": [],
            "design_approach": None,
            "action_plan": [],
            "product_requirements": [],
            "warnings": [{
                "severity": "critical",
                "title": "Advice Generation Failed",
                "message": f"Unable to generate design advice: {error}",
            }],
            "seasonal_notes": None,
            "_metadata": {
                "error": error,
            },
        }


# Singleton instance
yard_advisor_service = YardAdvisorService()
