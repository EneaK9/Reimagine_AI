"""
Scenario context assembly service.
Selects only the relevant scenario chunks based on user inputs,
reducing token usage from ~25k to ~3-6k.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from ..data import (
    SCENARIO_CHUNKS,
    ALWAYS_INCLUDE_CHUNKS,
    CHUNK_INDEX,
    get_dimension_key,
    get_budget_key,
    get_climate_from_city,
    lookup_chunks,
)


@dataclass
class AssembledContext:
    """Result of assembling relevant scenario chunks."""
    chunks: List[Dict[str, Any]]
    chunk_ids: List[str]
    total_tokens: int
    truncated: bool = False


@dataclass
class YardInputs:
    """
    Lightweight input container for context assembly.
    All fields are optional - the service works with whatever is provided.
    """
    unit_system: Optional[str] = None
    yard_length: Optional[float] = None
    yard_width: Optional[float] = None
    dimensions_sqm: Optional[float] = None
    orientation: Optional[str] = None
    surface_type: Optional[str] = None
    slope: Optional[str] = None
    city_or_region: Optional[str] = None
    city_context: Optional[str] = None
    environment_type: Optional[str] = None
    primary_purpose: Optional[str] = None
    who_uses: Optional[List[str]] = None
    maintenance: Optional[str] = None
    style_preference: Optional[str] = None
    ownership: Optional[str] = None
    budget: Optional[float] = None


class ScenarioContextService:
    """
    Assembles relevant scenario chunks based on user inputs.
    
    Instead of sending the full ~25k token scenarios document to the LLM,
    this service selects only the chunks that apply to the user's specific
    situation, typically reducing context to ~3-6k tokens.
    """
    
    def __init__(self):
        self.chunks = SCENARIO_CHUNKS
        self.index = CHUNK_INDEX
        self.always_include = ALWAYS_INCLUDE_CHUNKS
        # Rough estimate: 1 token ≈ 4 characters
        self.chars_per_token = 4
    
    def assemble_context(
        self,
        inputs: YardInputs,
        max_tokens: int = 8000,
        extra_chunk_ids: Optional[List[str]] = None,
        dynamic_chunks: Optional[List[Dict[str, Any]]] = None,
    ) -> AssembledContext:
        """
        Assemble relevant scenario chunks based on user inputs.
        
        Args:
            inputs: User inputs (all fields optional)
            max_tokens: Maximum tokens to include in context
            
        Returns:
            AssembledContext with selected chunks and metadata
        """
        required_chunk_ids: Set[str] = set(self.always_include)
        
        # 1. Dimensions
        if inputs.dimensions_sqm is not None:
            size_key = get_dimension_key(inputs.dimensions_sqm)
            required_chunk_ids.update(lookup_chunks("dimensions", size_key))
        
        # 2. Orientation
        if inputs.orientation:
            required_chunk_ids.update(lookup_chunks("orientation", inputs.orientation))
        
        # 3. Surface type
        if inputs.surface_type:
            required_chunk_ids.update(lookup_chunks("surface_type", inputs.surface_type))
        
        # 4. Slope
        if inputs.slope:
            required_chunk_ids.update(lookup_chunks("slope", inputs.slope))
        
        # 5. Climate zone (derived from city)
        if inputs.city_or_region:
            climate_zone = get_climate_from_city(inputs.city_or_region)
            required_chunk_ids.update(lookup_chunks("climate_zone", climate_zone))
        
        # 6. Environment type
        if inputs.environment_type:
            required_chunk_ids.update(lookup_chunks("environment_type", inputs.environment_type))
        
        # 7. Who uses (multiple can apply)
        if inputs.who_uses:
            for user_type in inputs.who_uses:
                required_chunk_ids.update(lookup_chunks("who_uses", user_type))
        
        # 8. Primary purpose
        if inputs.primary_purpose:
            required_chunk_ids.update(lookup_chunks("primary_purpose", inputs.primary_purpose))
        
        # 9. Maintenance
        if inputs.maintenance:
            required_chunk_ids.update(lookup_chunks("maintenance", inputs.maintenance))
        
        # 10. Ownership
        if inputs.ownership:
            required_chunk_ids.update(lookup_chunks("ownership", inputs.ownership))
        
        # 11. Budget tier
        if inputs.budget is not None:
            budget_key = get_budget_key(inputs.budget)
            required_chunk_ids.update(lookup_chunks("budget_tier", budget_key))
        
        # 12. Style preference
        if inputs.style_preference:
            required_chunk_ids.update(lookup_chunks("style_preference", inputs.style_preference))

        # 13. Extra chunk IDs (e.g., 2.3 climate overrides)
        if extra_chunk_ids:
            required_chunk_ids.update(extra_chunk_ids)
        
        # Collect chunks into a dict so dynamic chunks can override static ones by id.
        chunks_by_id: Dict[str, Dict[str, Any]] = {}
        for chunk_id in required_chunk_ids:
            if chunk_id in self.chunks:
                chunks_by_id[chunk_id] = self.chunks[chunk_id]

        # Add or override with dynamic chunks (e.g., populated 2.4.site_palette)
        if dynamic_chunks:
            for chunk in dynamic_chunks:
                chunk_id = chunk.get("id")
                if not chunk_id:
                    continue
                chunks_by_id[str(chunk_id)] = chunk

        # Collect and sort chunks by priority (higher first)
        chunks = list(chunks_by_id.values())
        
        chunks.sort(key=lambda c: c.get("priority", 0), reverse=True)
        
        # Trim to fit token budget
        assembled_chunks = []
        total_chars = 0
        max_chars = max_tokens * self.chars_per_token
        truncated = False
        
        for chunk in chunks:
            chunk_chars = len(chunk.get("content", ""))
            if total_chars + chunk_chars > max_chars:
                truncated = True
                # Try to include at least the core rules
                if chunk["id"] in self.always_include:
                    assembled_chunks.append(chunk)
                    total_chars += chunk_chars
                continue
            assembled_chunks.append(chunk)
            total_chars += chunk_chars
        
        return AssembledContext(
            chunks=assembled_chunks,
            chunk_ids=[c["id"] for c in assembled_chunks],
            total_tokens=total_chars // self.chars_per_token,
            truncated=truncated,
        )
    
    def format_for_prompt(self, context: AssembledContext) -> str:
        """
        Format assembled chunks into a prompt-ready string.
        
        Args:
            context: AssembledContext from assemble_context()
            
        Returns:
            Formatted string ready to include in LLM prompt
        """
        sections = []
        for chunk in context.chunks:
            title = chunk.get("title", "Untitled")
            content = chunk.get("content", "")
            sections.append(f"### {title}\n\n{content}")
        
        return "\n\n---\n\n".join(sections)
    
    def get_applicable_warnings(self, inputs: YardInputs) -> List[str]:
        """
        Extract any warnings from the applicable chunks.
        
        Args:
            inputs: User inputs
            
        Returns:
            List of warning strings
        """
        context = self.assemble_context(inputs)
        warnings = []
        
        for chunk in context.chunks:
            content = chunk.get("content", "")
            # Look for "Typical warning:" or "warning:" patterns
            if "Typical warning:" in content:
                start = content.find("Typical warning:")
                end = content.find("\n", start)
                if end == -1:
                    end = len(content)
                warning_text = content[start + len("Typical warning:"):end].strip()
                # Remove surrounding quotes if present
                if warning_text.startswith('"') and warning_text.endswith('"'):
                    warning_text = warning_text[1:-1]
                warnings.append(warning_text)
        
        return warnings
    
    def has_inputs(self, inputs: YardInputs) -> bool:
        """
        Check if any yard-specific inputs were provided.
        
        Args:
            inputs: User inputs
            
        Returns:
            True if at least one input field is set
        """
        return any([
            inputs.yard_length is not None,
            inputs.yard_width is not None,
            inputs.dimensions_sqm is not None,
            inputs.orientation,
            inputs.surface_type,
            inputs.slope,
            inputs.city_or_region,
            inputs.environment_type,
            inputs.primary_purpose,
            inputs.who_uses,
            inputs.maintenance,
            inputs.style_preference,
            inputs.ownership,
            inputs.budget is not None,
        ])
    
    def summarize_inputs(self, inputs: YardInputs) -> Dict[str, Any]:
        """
        Create a summary of the provided inputs for display.
        
        Args:
            inputs: User inputs
            
        Returns:
            Dictionary summarizing the inputs
        """
        summary = {}
        
        if inputs.unit_system:
            summary["unit_system"] = str(inputs.unit_system)

        if inputs.yard_length is not None or inputs.yard_width is not None:
            length = "" if inputs.yard_length is None else str(inputs.yard_length)
            width = "" if inputs.yard_width is None else str(inputs.yard_width)
            summary["yard_dimensions"] = f"{length} x {width}".strip()

        if inputs.dimensions_sqm is not None:
            summary["dimensions"] = f"{inputs.dimensions_sqm} m²"
        if inputs.orientation:
            summary["orientation"] = f"{inputs.orientation.capitalize()}-facing"
        if inputs.surface_type:
            summary["surface"] = inputs.surface_type.replace("_", " ").title()
        if inputs.slope:
            summary["slope"] = inputs.slope.replace("_", " ").title()
        if inputs.city_or_region:
            summary["location"] = inputs.city_or_region
            summary["climate"] = get_climate_from_city(inputs.city_or_region).title()
        if inputs.environment_type:
            summary["environment"] = inputs.environment_type.replace("_", " ").title()
        if inputs.primary_purpose:
            summary["purpose"] = inputs.primary_purpose.replace("_", " ").title()
        if inputs.who_uses:
            summary["users"] = ", ".join(inputs.who_uses)
        if inputs.maintenance:
            summary["maintenance"] = inputs.maintenance.replace("_", " ").title()
        if inputs.style_preference:
            summary["style"] = inputs.style_preference.replace("_", " ").title()
        if inputs.ownership:
            summary["ownership"] = inputs.ownership.title()
        if inputs.budget is not None:
            summary["budget"] = f"${inputs.budget:,.0f}"
        
        return summary


# Singleton instance
scenario_context_service = ScenarioContextService()
