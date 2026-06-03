"""
Chunk index mapping user input values to relevant scenario chunk IDs.
This enables efficient lookup of only the chunks that apply to a user's situation.
"""

from typing import Dict, List

# Maps input field name -> input value -> list of chunk IDs
CHUNK_INDEX: Dict[str, Dict[str, List[str]]] = {
    # ========== MODULE 1.1 - DIMENSIONS ==========
    "dimensions": {
        "under_15": ["1.1.micro_yard"],
        "15_to_40": ["1.1.small_garden"],
        "40_to_100": ["1.1.medium_garden"],
        "over_100": ["1.1.large_garden"],
    },
    
    # ========== MODULE 1.2 - ORIENTATION ==========
    "orientation": {
        "north": ["1.2.north_facing"],
        "south": ["1.2.south_facing"],
        "east": ["1.2.east_facing"],
        "west": ["1.2.west_facing"],
    },
    
    # ========== MODULE 1.3 - SURFACE TYPE ==========
    "surface_type": {
        "grass": ["1.3.grass"],
        "concrete": ["1.3.concrete_paving"],
        "paving": ["1.3.concrete_paving"],
        "bare_soil": ["1.3.bare_soil"],
        "gravel": ["1.3.gravel"],
        "decking": ["1.3.decking"],
        "mixed": ["1.3.mixed"],
    },
    
    # ========== MODULE 1.4 - SLOPE ==========
    "slope": {
        "flat": ["1.4.flat"],
        "gentle": ["1.4.gentle_slope"],
        "significant": ["1.4.significant_slope"],
    },
    
    # ========== MODULE 2.1 - CLIMATE ZONE ==========
    "climate_zone": {
        "cold": ["2.1.cold_climate"],
        "temperate": ["2.1.temperate_climate"],
        "warm": ["2.1.warm_subtropical"],
        "tropical": ["2.1.tropical_humid"],
        "arid": ["2.1.arid_desert"],
    },
    
    # ========== MODULE 2.2 - ENVIRONMENT TYPE ==========
    "environment_type": {
        "coastal": ["2.2.coastal"],
        "suburban": ["2.2.suburban"],
        "urban": ["2.2.urban"],
        "rural": ["2.2.rural"],
        "mountain": ["2.2.mountain"],
    },
    
    # ========== MODULE 3.1 - WHO USES THE SPACE ==========
    "who_uses": {
        "children": ["3.1.children"],
        "dogs": ["3.1.dogs"],
        "cats": ["3.1.cats"],
        "elderly": ["3.1.elderly"],
        "entertaining": ["3.1.entertaining"],
        "guests": ["3.1.entertaining"],
        "solo": ["3.1.solo"],
        "adults": [],  # No special rules for adults only
    },
    
    # ========== MODULE 3.2 - PRIMARY PURPOSE ==========
    "primary_purpose": {
        "dining": ["3.2.dining"],
        "relaxing": ["3.2.relaxing"],
        "lounging": ["3.2.relaxing"],
        "children_play": ["3.2.children_play"],
        "play": ["3.2.children_play"],
        "food_growing": ["3.2.food_growing"],
        "vegetables": ["3.2.food_growing"],
        "aesthetic": ["3.2.aesthetic"],
        "show_garden": ["3.2.aesthetic"],
    },
    
    # ========== MODULE 3.3 - MAINTENANCE ==========
    "maintenance": {
        "low": ["3.3.low_maintenance"],
        "medium": ["3.3.medium_maintenance"],
        "high": ["3.3.high_maintenance"],
    },
    
    # ========== MODULE 3.4 - OWNERSHIP ==========
    "ownership": {
        "owner": ["3.4.homeowner"],
        "homeowner": ["3.4.homeowner"],
        "renter": ["3.4.renter"],
        "rent": ["3.4.renter"],
    },
    
    # ========== MODULE 4 - BUDGET ==========
    "budget_tier": {
        "under_300": ["4.1.budget_under_300"],
        "300_to_1000": ["4.2.budget_300_1000"],
        "1000_to_3000": ["4.3.budget_1000_3000"],
        "over_3000": ["4.4.budget_over_3000"],
    },
    
    # ========== MODULE 5 - STYLE ==========
    "style_preference": {
        "modern": ["5.1.modern_minimal"],
        "minimal": ["5.1.modern_minimal"],
        "rustic": ["5.1.rustic_cottage"],
        "cottage": ["5.1.rustic_cottage"],
        "natural": ["5.1.rustic_cottage"],
        "industrial": ["5.1.industrial"],
        "coastal": ["5.1.coastal_hamptons"],
        "hamptons": ["5.1.coastal_hamptons"],
        "tropical": ["5.1.tropical_lush"],
        "lush": ["5.1.tropical_lush"],
        "mediterranean": ["5.1.mediterranean"],
        "scandinavian": ["5.1.scandinavian"],
    },
}


# City to climate zone mapping (simplified - expand as needed)
CITY_CLIMATE_MAP: Dict[str, str] = {
    # Cold (USDA Zone 3-5)
    "minneapolis": "cold",
    "minnesota": "cold",
    "wisconsin": "cold",
    "milwaukee": "cold",
    "maine": "cold",
    "portland maine": "cold",
    "toronto": "cold",
    "montreal": "cold",
    "canada": "cold",
    "stockholm": "cold",
    "oslo": "cold",
    "helsinki": "cold",
    "edinburgh": "cold",
    "aberdeen": "cold",
    
    # Temperate (USDA Zone 6-8)
    "new york": "temperate",
    "nyc": "temperate",
    "chicago": "temperate",
    "boston": "temperate",
    "seattle": "temperate",
    "portland": "temperate",
    "portland oregon": "temperate",
    "denver": "temperate",
    "london": "temperate",
    "uk": "temperate",
    "england": "temperate",
    "paris": "temperate",
    "france": "temperate",
    "berlin": "temperate",
    "germany": "temperate",
    "amsterdam": "temperate",
    "netherlands": "temperate",
    "dublin": "temperate",
    "ireland": "temperate",
    "auckland": "temperate",
    "new zealand": "temperate",
    "melbourne": "temperate",
    "sydney": "temperate",
    "tokyo": "temperate",
    
    # Warm/Subtropical (USDA Zone 9-10)
    "miami": "warm",
    "florida": "warm",
    "tampa": "warm",
    "orlando": "warm",
    "houston": "warm",
    "texas": "warm",
    "dallas": "warm",
    "austin": "warm",
    "san antonio": "warm",
    "los angeles": "warm",
    "la": "warm",
    "san diego": "warm",
    "southern california": "warm",
    "atlanta": "warm",
    "georgia": "warm",
    "barcelona": "warm",
    "spain": "warm",
    "madrid": "warm",
    "rome": "warm",
    "italy": "warm",
    "greece": "warm",
    "athens": "warm",
    "lisbon": "warm",
    "portugal": "warm",
    "brisbane": "warm",
    "perth": "warm",
    
    # Tropical/Humid (USDA Zone 11+)
    "hawaii": "tropical",
    "honolulu": "tropical",
    "puerto rico": "tropical",
    "san juan": "tropical",
    "singapore": "tropical",
    "bali": "tropical",
    "thailand": "tropical",
    "bangkok": "tropical",
    "vietnam": "tropical",
    "philippines": "tropical",
    "manila": "tropical",
    "cairns": "tropical",
    "darwin": "tropical",
    
    # Arid/Desert (USDA Zone 9-13, low rainfall)
    "phoenix": "arid",
    "arizona": "arid",
    "tucson": "arid",
    "las vegas": "arid",
    "nevada": "arid",
    "albuquerque": "arid",
    "new mexico": "arid",
    "dubai": "arid",
    "uae": "arid",
    "saudi arabia": "arid",
    "riyadh": "arid",
    "israel": "arid",
    "tel aviv": "arid",
    "alice springs": "arid",
}


def get_dimension_key(sqm: float) -> str:
    """Convert square meters to dimension category key."""
    if sqm < 15:
        return "under_15"
    elif sqm < 40:
        return "15_to_40"
    elif sqm < 100:
        return "40_to_100"
    else:
        return "over_100"


def get_budget_key(budget: float) -> str:
    """Convert budget amount to budget tier key."""
    if budget < 300:
        return "under_300"
    elif budget < 1000:
        return "300_to_1000"
    elif budget < 3000:
        return "1000_to_3000"
    else:
        return "over_3000"


def get_climate_from_city(city: str) -> str:
    """
    Derive climate zone from city name.
    Returns 'temperate' as default if city not found.
    """
    city_lower = city.lower().strip()
    
    # Direct lookup
    if city_lower in CITY_CLIMATE_MAP:
        return CITY_CLIMATE_MAP[city_lower]
    
    # Partial match
    for known_city, climate in CITY_CLIMATE_MAP.items():
        if known_city in city_lower or city_lower in known_city:
            return climate
    
    # Default to temperate (most common)
    return "temperate"


def lookup_chunks(field: str, value: str) -> List[str]:
    """
    Look up chunk IDs for a given field and value.
    Returns empty list if field or value not found.
    """
    field_index = CHUNK_INDEX.get(field, {})
    return field_index.get(value.lower() if isinstance(value, str) else value, [])
