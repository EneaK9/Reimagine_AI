"""
Location intelligence service.

Derives a structured climate/location profile from a City/Region string plus a
simple city context selector (coastal vs inland vs unknown).

This is intentionally LLM-based (no external climate APIs). We validate and
normalize the output for safe downstream use (2.3 override chunks and 2.4 palette).
"""

import json
from typing import Any, Dict, Optional, Tuple

from openai import AsyncOpenAI

from ..config import get_settings
from ..models.schemas import CityContext, LocationProfile

settings = get_settings()


LOCATION_INTELLIGENCE_SYSTEM_PROMPT = """You are an expert landscape architect and horticultural consultant with deep knowledge of climate science, plant hardiness, and outdoor material performance.

Return ONLY valid JSON. No markdown. No comments. No trailing commas.

CRITICAL RULE FOR AMBIGUOUS CITY NAMES:
When a city name exists in multiple countries (e.g., Naples, Paris, London, Valencia, Athens), ALWAYS default to the most globally famous or historically significant city:
- Naples → Naples, Italy (NOT Naples, Florida)
- Paris → Paris, France (NOT Paris, Texas)
- London → London, UK (NOT London, Ontario)
- Valencia → Valencia, Spain (NOT Valencia, California)
- Athens → Athens, Greece (NOT Athens, Georgia)
- Venice → Venice, Italy (NOT Venice, Florida)
- Milan → Milan, Italy (NOT Milan, Michigan)
Only use the US/other version if the user explicitly specifies (e.g., "Naples, FL" or "Naples, Florida").

Be specific with numbers — do not use ranges unless ranges are genuinely the only accurate answer.
If the city has meaningful coastal vs inland variation, flag it and answer for the most common residential context.
"""


def _location_intelligence_user_prompt(
    *,
    city_or_region: str,
    city_context: Optional[CityContext],
) -> str:
    context = city_context.value if isinstance(city_context, CityContext) else (city_context or "unknown")
    return f"""The location: {city_or_region}
City context: {context} (coastal vs inland vs unknown)

Return a complete location climate profile as JSON matching this schema:
{{
  "city": "string",
  "country_or_region": "string or null",
  "city_context": "coastal|inland|unknown",
  "usda_hardiness_zone": "string or null",
  "annual_rainfall_mm": 0,
  "monthly_rainfall_mm": [12 numbers for Jan..Dec] or null,
  "summer_dry_months": ["strings like 'Jun'"] or null,
  "irrigation_required": "mandatory|recommended|not_needed",
  "july_avg_high_c": 0,
  "july_avg_high_f": 0,
  "shade_structure_priority": "mandatory|recommended|optional",
  "last_spring_frost_date": "string or null (e.g. 'Apr 12')",
  "first_autumn_frost_date": "string or null (e.g. 'Oct 28')",
  "first_frost_month": 1-12,
  "growing_season_days": 0,
  "annual_sunshine_hours": 0,
  "solar_lighting_viability": "year_round|summer_only|not_recommended",
  "uv_index_summer": 0,
  "uv_rated_materials_required": "mandatory|recommended|standard",
  "summer_humidity_pct": 0,
  "humidity_risk_level": "low|moderate|high|tropical",
  "avg_wind_kmh": 0,
  "prevailing_wind_direction": "string or null",
  "wind_risk_level": "low|moderate|high",
  "elevation_m": 0,
  "uv_altitude_adjustment_needed": "yes|no",
  "uv_altitude_uplift_pct": 0,
  "special_flags": ["strings"],
  "plant_hardiness_summary": "string or null",
  "material_durability_summary": "string or null",
  "data_quality": "high|medium|low",
  "assumptions": ["strings"]
}}
"""


class LocationIntelligenceService:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.gpt_model
        self._cache: Dict[str, LocationProfile] = {}

    async def get_location_profile(
        self,
        *,
        city_or_region: str,
        city_context: Optional[CityContext] = None,
    ) -> LocationProfile:
        cache_key = self._cache_key(city_or_region, city_context)
        if cache_key in self._cache:
            return self._cache[cache_key]

        user_prompt = _location_intelligence_user_prompt(
            city_or_region=city_or_region,
            city_context=city_context,
        )

        # First attempt
        profile = await self._call_model(user_prompt)
        issues = self._validate_profile(profile)
        if issues:
            # One repair attempt: ask the model to correct only the invalid fields
            repair_prompt = (
                user_prompt
                + "\n\nThe JSON had validation issues. Fix ONLY these issues and return corrected JSON:\n"
                + "\n".join(f"- {issue}" for issue in issues)
            )
            profile = await self._call_model(repair_prompt)
            issues = self._validate_profile(profile)

        # Best-effort normalization even if issues remain
        profile = self._normalize_profile(profile)
        self._cache[cache_key] = profile
        return profile

    def build_site_palette_text(self, profile: LocationProfile) -> str:
        """
        Render a populated Site Palette block for injection into the dynamic 2.4 chunk
        and into PLANT_BRIEF_PROMPT.
        """
        city = profile.city
        country = profile.country_or_region or ""
        climate_class = profile.usda_hardiness_zone or "Unknown"
        growing_season = profile.growing_season_days or "Unknown"
        last_frost = profile.last_spring_frost_date or "Unknown"
        first_frost = profile.first_autumn_frost_date or "Unknown"
        drought = (
            "Irrigation required"
            if profile.irrigation_required == "mandatory"
            else (profile.irrigation_required or "Unknown")
        )
        summer_high = profile.july_avg_high_c if profile.july_avg_high_c is not None else "Unknown"
        uv = profile.uv_index_summer if profile.uv_index_summer is not None else "Unknown"
        humidity = profile.summer_humidity_pct if profile.summer_humidity_pct is not None else "Unknown"
        wind = profile.avg_wind_kmh if profile.avg_wind_kmh is not None else "Unknown"
        wind_dir = profile.prevailing_wind_direction or "Unknown"

        return (
            f"SITE PALETTE — {city}, {country}".strip().rstrip(",")
            + "\n"
            + f"Climate class: {climate_class}\n"
            + f"Growing season: {growing_season} (Last frost: {last_frost} / First frost: {first_frost})\n"
            + f"Summer drought status: {drought}\n"
            + f"Summer high: {summer_high}°C\n"
            + f"UV: {uv}\n"
            + f"Humidity: {humidity}%RH\n"
            + f"Wind: {wind}km/h prevailing {wind_dir}\n\n"
            + "VIABLE PLANT CATEGORIES:\n"
            + "✓ [Category] — [one-line reason why it works here]\n\n"
            + "EXCLUDED PLANT CATEGORIES:\n"
            + "✗ [Category] — [one-line reason why it fails here]\n"
        )

    async def _call_model(self, user_prompt: str) -> LocationProfile:
        response = await self.client.chat.completions.create(
            model=self.model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": LOCATION_INTELLIGENCE_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=1200,
            temperature=0.2,
        )
        data = self._load_json(response.choices[0].message.content or "{}")
        # Sanitize month fields: 0 means "no frost" in some AI responses, convert to None
        if data.get("first_frost_month") == 0:
            data["first_frost_month"] = None
        return LocationProfile(**data)

    def _cache_key(
        self,
        city_or_region: str,
        city_context: Optional[CityContext],
    ) -> str:
        context = city_context.value if isinstance(city_context, CityContext) else (city_context or "unknown")
        return f"{city_or_region.strip().lower()}|{context}"

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

    def _validate_profile(self, profile: LocationProfile) -> list:
        issues = []
        if profile.monthly_rainfall_mm is not None and len(profile.monthly_rainfall_mm) != 12:
            issues.append("monthly_rainfall_mm must be a list of 12 numbers (Jan..Dec) or null")
        if profile.first_frost_month is not None and not (1 <= profile.first_frost_month <= 12):
            issues.append("first_frost_month must be 1..12")
        if profile.summer_humidity_pct is not None and not (0 <= profile.summer_humidity_pct <= 100):
            issues.append("summer_humidity_pct must be 0..100")
        if profile.uv_index_summer is not None and not (0 <= profile.uv_index_summer <= 14):
            issues.append("uv_index_summer must be 0..14")
        if profile.annual_sunshine_hours is not None and profile.annual_sunshine_hours > 5000:
            issues.append("annual_sunshine_hours seems unrealistic (>5000)")
        return issues

    def _normalize_profile(self, profile: LocationProfile) -> LocationProfile:
        # If monthly rainfall isn't the expected length, drop it.
        if profile.monthly_rainfall_mm is not None and len(profile.monthly_rainfall_mm) != 12:
            profile.monthly_rainfall_mm = None
        return profile


location_intelligence_service = LocationIntelligenceService()

