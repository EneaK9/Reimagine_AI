"""
Parsed scenario chunks from yard_designer_scenarios.md.
Each chunk is a self-contained rule with metadata for retrieval.
"""

from typing import Dict, List, Any

# Type alias for chunk structure
Chunk = Dict[str, Any]

# Always-include chunks (core rules)
ALWAYS_INCLUDE_CHUNKS = ["0.0.cardinal_rules", "0.1.budget_split"]

SCENARIO_CHUNKS: Dict[str, Chunk] = {
    # ========== CORE RULES (ALWAYS INCLUDE) ==========
    
    "0.0.cardinal_rules": {
        "id": "0.0.cardinal_rules",
        "module": "0.0",
        "title": "Cardinal Rules",
        "priority": 100,
        "tags": ["core", "always"],
        "content": """## Cardinal Rules — Always Follow

1. Never recommend a product without knowing real dimensions. A product that doesn't fit is worse than no product.
2. Never exceed the stated budget — including delivery, assembly, and accessories.
3. Never recommend a product without verifying it is in stock and deliverable.
4. Never generate the final image before verifying product sizes and spatial fit.
5. Never fight existing conditions — sun exposure, climate, surface type are constraints, not backgrounds.""",
    },
    
    "0.1.budget_split": {
        "id": "0.1.budget_split",
        "module": "0.1",
        "title": "Budget Split Rules",
        "priority": 99,
        "tags": ["core", "budget", "always"],
        "content": """## Budget Split Rules

Apply the 60/30/10 split:
- 60% on structural items (furniture, pergola, large planters)
- 30% on soft elements (planting, cushions, lighting, accessories)
- 10% held as cost buffer — never spend upfront

Always present three tiers when possible:
- Best value — lowest cost that functionally works
- Recommended — best quality-to-price ratio
- Premium — what a professional would specify""",
    },

    # ========== MODULE 1.1 - DIMENSIONS ==========
    
    "1.1.micro_yard": {
        "id": "1.1.micro_yard",
        "module": "1.1",
        "title": "Under 15 m² (micro yard, small balcony, tiny patio)",
        "priority": 10,
        "tags": ["space", "dimensions", "small", "constraints"],
        "content": """## Space: Under 15 m²

Every product must justify its footprint. There is no room for duplication or decorative-only items.

**Design rules:**
- Maximum 1 large piece of furniture (a bistro set OR a small sofa, never both)
- All planters must be vertical, wall-mounted, or railing-mounted — never floor planters
- No pergolas, gazebos, or overhead structures
- Foldable or stackable furniture is strongly preferred
- No lawns, no gravel paths — surface treatment is one material only
- Minimum 90cm clear circulation path must be preserved

**Product search filters:**
- Filter for "balcony", "small space", "compact", "foldable", "stackable"
- Maximum table diameter 70cm (round) or 60×90cm (rectangular)
- Prioritize wall-mounted planters, railing planters, vertical garden panels
- Lighting: string lights, solar stake lights, or clip-on — no large floor lamps

**Image generation:**
- Wide-angle from doorway looking out
- Show furniture in use so user understands livability
- Negative space must be visible — never pack the visualization

**Typical warning:** "This space is under 15m². We've prioritized products that keep circulation clear and avoid overwhelming the area."
""",
    },
    
    "1.1.small_garden": {
        "id": "1.1.small_garden",
        "module": "1.1",
        "title": "15–40 m² (small garden, average urban backyard)",
        "priority": 10,
        "tags": ["space", "dimensions", "small"],
        "content": """## Space: 15–40 m²

The most common residential garden size. Enough room for a defined seating area plus one or two additional zones.

**Design rules:**
- Maximum 2 defined zones (e.g. dining area + planting zone, or seating area + lawn)
- One statement piece allowed (fire pit, water feature, statement planter, pergola over dining)
- Lawn should not exceed 50% of total space if other zones included
- Paths between zones minimum 90cm wide
- Fence or boundary treatment on at least one wall

**Product search filters:**
- Standard residential furniture sizing appropriate
- Look for modular options (reconfigurable sofa sets)
- Include boundary/privacy products in recommendations

**Image generation:**
- 3/4 overhead angle showing both zones simultaneously
- Include human scale reference
""",
    },
    
    "1.1.medium_garden": {
        "id": "1.1.medium_garden",
        "module": "1.1",
        "title": "40–100 m² (medium garden, suburban backyard)",
        "priority": 10,
        "tags": ["space", "dimensions", "medium"],
        "content": """## Space: 40–100 m²

Enough space for genuine landscape design with multiple zones, a lawn, and structural planting.

**Design rules:**
- Up to 3 defined zones (e.g. dining terrace + lawn + planting border)
- A dedicated lawn area is appropriate — recommend lawn treatment if existing grass is poor
- At least one vertical element required (pergola, trellis, tall specimen plant, privacy screen)
- Lighting design becomes important — zone the lighting across areas
- A focal point is mandatory (statement tree, water feature, sculpture, or fire pit)

**Product search filters:**
- Full-size dining sets (6-seater) appropriate
- Separate lounge and dining furniture sets are viable
- Include raised beds, large planters, border edging
- Outdoor rugs appropriate for defining seating zones

**Image generation:**
- Perspective view from one corner showing full depth and width
- Show all zones with clear visual separation
- Include a sense of journey — path or lawn leading to the focal point
""",
    },
    
    "1.1.large_garden": {
        "id": "1.1.large_garden",
        "module": "1.1",
        "title": "Over 100 m² (large garden, estate-scale)",
        "priority": 10,
        "tags": ["space", "dimensions", "large"],
        "content": """## Space: Over 100 m²

Multiple distinct rooms. Retail products may be insufficient for the full space — professional landscaping elements may be needed.

**Design rules:**
- Divide into minimum 3 rooms/zones — each with its own purpose and furniture set
- Hard landscaping (paving, gravel, decking) should define zone boundaries
- Trees are appropriate as structural elements — include at least one if none exist
- Irrigation system should be recommended for significant planting
- Lighting design must cover all zones — pathway, zone, and feature lighting

**Product search filters:**
- Commercial or semi-commercial grade furniture for high-use areas
- Search for "garden room dividers", "outdoor rugs large", "garden arches", "pergola kits"
- Water features can be larger — pond kits, wall fountains, freestanding features

**Typical warning:** "At this scale, some elements (paving, large structures, lawn preparation) may require professional installation."
""",
    },

    # ========== MODULE 1.2 - ORIENTATION ==========
    
    "1.2.north_facing": {
        "id": "1.2.north_facing",
        "module": "1.2",
        "title": "North-facing (Northern Hemisphere)",
        "priority": 9,
        "tags": ["orientation", "shade", "light", "plants"],
        "content": """## Orientation: North-facing

Receives little to no direct sun for most of the year. The coldest, most challenging orientation.

**Plant rules:**
- Only shade-tolerant species: ferns, hostas, astilbe, hellebores, hydrangeas, ivy, fatsia japonica
- No Mediterranean plants (lavender, rosemary, cistus, agapanthus) — they require full sun
- No vegetable growing unless there is a sunny corner
- Prioritize plants with interesting foliage over flowers

**Material rules:**
- Recommend lighter-coloured furniture and surfaces to reflect available light
- Avoid dark timber decking — looks permanently damp and cold
- Light-toned gravel, pale paving, or light wood decking recommended

**Structural rules:**
- No pergola over main seating area — makes shaded space feel like a cave
- Glass or perspex screening preferred over solid fencing
- Mirror panels on walls can dramatically increase perceived brightness

**Image generation:**
- Bright overcast light setting (not harsh midday sun)
- Keep product color palette light and airy

**Typical warning:** "Your garden faces north, which means limited direct sunlight. We've selected shade-tolerant plants and lighter-toned products."
""",
    },
    
    "1.2.south_facing": {
        "id": "1.2.south_facing",
        "module": "1.2",
        "title": "South-facing (Northern Hemisphere)",
        "priority": 9,
        "tags": ["orientation", "sun", "light", "plants"],
        "content": """## Orientation: South-facing

Maximum sun throughout the day. The most desirable orientation in temperate climates. Can become extremely hot in warm climates.

**Plant rules:**
- The widest range of plants is viable — Mediterranean, cottage garden, prairie, tropical
- In hot climates: include drought-tolerant species (lavender, sedum, salvia, ornamental grasses)
- Include at least one plant that provides shade or screening if space is large

**Material rules:**
- UV resistance ratings are critical — check all cushion fabrics, plastics, and composites
- Dark metal furniture will become dangerously hot — recommend light-coloured metal or wood/composite
- Consider shade sail or pergola with canopy in warm climates

**Structural rules:**
- Shade structure (pergola, sail shade, parasol) should be a primary product, not an afterthought
- Position seating to have access to both sun and shade

**Image generation:**
- Warm afternoon sunlight with clear shadows showing depth
- Show shade structure in use if included
""",
    },
    
    "1.2.east_facing": {
        "id": "1.2.east_facing",
        "module": "1.2",
        "title": "East-facing",
        "priority": 9,
        "tags": ["orientation", "morning", "light", "plants"],
        "content": """## Orientation: East-facing

Morning sun, afternoon shade. Ideal for breakfast spaces. Hot summer afternoons are naturally shaded.

**Plant rules:**
- Suitable for most cottage garden plants, roses (prefer morning sun to dry dew), many shrubs
- Avoid very sun-hungry plants that need all-day sun — agapanthus, bougainvillea, most vegetables
- Good for moisture-loving plants, but check for fungal disease risk

**Design rules:**
- Position primary seating to capture morning sun — the best hours in this orientation
- Ideal orientation for a breakfast terrace or morning coffee area
- Include a covered area if user uses the space in the evening

**Image generation:**
- Morning light setting — low golden sun from the east, long shadows pointing west
""",
    },
    
    "1.2.west_facing": {
        "id": "1.2.west_facing",
        "module": "1.2",
        "title": "West-facing",
        "priority": 9,
        "tags": ["orientation", "evening", "light", "plants"],
        "content": """## Orientation: West-facing

Afternoon and evening sun. The best orientation for evening entertaining. Can be hot in summer afternoons.

**Plant rules:**
- Similar to south-facing, but plants must tolerate intense afternoon/evening sun
- Excellent for evening-use plants: night-scented stock, jasmine, nicotiana
- Avoid plants that wilt in afternoon heat without consistent watering

**Design rules:**
- Prime orientation for outdoor dining and evening entertaining — design around it
- Lighting is secondary to sun management — evening sun provides natural atmosphere
- Shade sail or large parasol recommended for the 2–5pm window in summer

**Image generation:**
- Warm evening/golden hour light setting
- Show lighting products switched on even in the evening image
""",
    },

    # ========== MODULE 1.3 - SURFACE TYPE ==========
    
    "1.3.grass": {
        "id": "1.3.grass",
        "module": "1.3",
        "title": "Grass / Lawn",
        "priority": 8,
        "tags": ["surface", "grass", "lawn"],
        "content": """## Surface: Grass / Lawn

Freestanding products only unless user is willing to remove or cut into turf. Furniture may sink into soft ground.

**Product rules:**
- Recommend furniture feet pads or ground protectors for metal or heavy furniture
- No ground-anchored pergola without confirming user willing to dig into lawn
- Raised beds need a membrane layer underneath
- Recommend lawn-edge products (steel edging, plastic border) to define zones
- If lawn is poor: include lawn repair kit, overseeding product, or artificial grass option

**Installation note:** "Furniture placed directly on grass may sink after rain. We recommend furniture foot pads or ground-level paving slabs under each leg."
""",
    },
    
    "1.3.concrete_paving": {
        "id": "1.3.concrete_paving",
        "module": "1.3",
        "title": "Concrete / Paving (existing)",
        "priority": 8,
        "tags": ["surface", "concrete", "paving", "patio"],
        "content": """## Surface: Concrete / Paving

The most flexible surface for product placement. Anchor points may be available. No ground preparation needed.

**Product rules:**
- Adhesive or bolt-down anchor systems available for pergolas and screens
- Outdoor rugs strongly recommended to define zones and add warmth
- Respect drainage — never block existing drain covers
- Check paving condition: include paving paint, patio cleaner, or crack filler if needed
""",
    },
    
    "1.3.bare_soil": {
        "id": "1.3.bare_soil",
        "module": "1.3",
        "title": "Bare Soil / Mud",
        "priority": 8,
        "tags": ["surface", "soil", "mud", "preparation"],
        "content": """## Surface: Bare Soil / Mud

Ground preparation is required before any product can be properly placed.

**Mandatory first recommendations:**
- Ground cover solution: gravel, bark chip, paving slabs, or decking tiles
- Weed membrane under any loose material
- No furniture directly on bare soil — it will sink and become unusable in wet weather

**Design rule:** Always include a surface treatment product as Priority 1, before any furniture or planting recommendation.
""",
    },
    
    "1.3.gravel": {
        "id": "1.3.gravel",
        "module": "1.3",
        "title": "Gravel (existing)",
        "priority": 8,
        "tags": ["surface", "gravel"],
        "content": """## Surface: Gravel

Good drainage, clean base, minimal work needed.

**Product rules:**
- Use ground plates or wide feet under furniture to prevent sinking
- Recommend edging to contain gravel if not present
- Raised beds and planters work well on gravel
- Adding more gravel or changing colour/grade is low cost and high impact
""",
    },
    
    "1.3.decking": {
        "id": "1.3.decking",
        "module": "1.3",
        "title": "Decking (existing)",
        "priority": 8,
        "tags": ["surface", "decking", "wood"],
        "content": """## Surface: Decking

Most versatile finished surface. Check condition before recommending anything heavy.

**Product rules:**
- Recommend decking oil or stain if boards look weathered — cheap high-impact improvement
- Weight limits may apply on raised decks — flag for large water features or heavy planters
- Non-slip strips recommended if there are steps or slopes
- No ground-anchored products without checking what's beneath the deck
""",
    },
    
    "1.3.mixed": {
        "id": "1.3.mixed",
        "module": "1.3",
        "title": "Mixed surfaces",
        "priority": 8,
        "tags": ["surface", "mixed"],
        "content": """## Surface: Mixed

Treat each zone separately using the rules for each surface type. Do not apply a single surface rule to the whole space.
""",
    },

    # ========== MODULE 1.4 - SLOPE ==========
    
    "1.4.flat": {
        "id": "1.4.flat",
        "module": "1.4",
        "title": "Flat",
        "priority": 7,
        "tags": ["slope", "flat", "level"],
        "content": """## Slope: Flat

No special considerations. Apply all other rules normally.
""",
    },
    
    "1.4.gentle_slope": {
        "id": "1.4.gentle_slope",
        "module": "1.4",
        "title": "Gentle slope (under 10°)",
        "priority": 7,
        "tags": ["slope", "gentle"],
        "content": """## Slope: Gentle (under 10°)

**Product rules:**
- Furniture with adjustable feet preferred — or include adjustable foot pads
- No large water features — they will tilt and leak
- Planting on slopes should include ground cover to prevent erosion (creeping thyme, sedum, vinca)
- Raised beds are excellent — they create level planting surfaces
""",
    },
    
    "1.4.significant_slope": {
        "id": "1.4.significant_slope",
        "module": "1.4",
        "title": "Significant slope (over 10°)",
        "priority": 7,
        "tags": ["slope", "steep", "terracing"],
        "content": """## Slope: Significant (over 10°)

Levelling or terracing is required before most products can be used safely.

**Rules:**
- Recommend terracing solution as Priority 1: railway sleepers, retaining wall blocks, or gabion baskets
- Any seating area must be on a levelled platform
- Steps or path with steps must be included if there is a level change
- Professional groundworks may be required

**Typical warning:** "Your garden has a significant slope. Before placing furniture or plants, a level platform or terracing solution is needed."
""",
    },

    # ========== MODULE 2.1 - CLIMATE ZONE ==========
    
    "2.1.cold_climate": {
        "id": "2.1.cold_climate",
        "module": "2.1",
        "title": "Cold climates — USDA Zone 3–5",
        "priority": 9,
        "tags": ["climate", "cold", "frost", "winter"],
        "content": """## Climate: Cold (USDA Zone 3–5)

Examples: Minnesota, Wisconsin, Maine, Canada, Northern UK, Scandinavia. Winter temperatures down to -40°C.

**Material rules — mandatory:**
- All furniture must be rated for sub-zero storage or storable indoors
- No concrete or ceramic planters unless rated "frost-proof" — terracotta will crack
- No water features unless pump rated for freeze/thaw or can be fully drained
- Only powder-coated steel, HDPE resin, teak, and ipe hardwood are appropriate year-round
- Cushions must be stored indoors — include outdoor storage product

**Plant rules:**
- Only plants rated for the zone or lower
- Evergreen structure: boxwood (Zone 4), yew, spruce, ornamental kale
- No Mediterranean plants — they won't survive winter
- Annual planting (replaced each season) is viable

**Design rules:**
- Design must work in summer AND winter
- Include storage solution for cushions and accessories
""",
    },
    
    "2.1.temperate_climate": {
        "id": "2.1.temperate_climate",
        "module": "2.1",
        "title": "Temperate climates — USDA Zone 6–8",
        "priority": 9,
        "tags": ["climate", "temperate", "four_seasons"],
        "content": """## Climate: Temperate (USDA Zone 6–8)

Examples: New York, Chicago, Pacific Northwest, UK, Western Europe, New Zealand. Four distinct seasons, frost common but not extreme.

**Material rules:**
- Most outdoor-rated materials are appropriate
- Cushions should be stored in autumn or kept in weatherproof storage
- Cast iron and untreated steel will rust — use powder-coated, galvanised, or stainless
- Frost-proof rating required for ceramics and concrete

**Plant rules:**
- Widest range available — cottage garden, prairie, woodland, Mediterranean (Zone 7–8)
- Include mix of seasonal interest: spring bulbs, summer perennials, autumn colour, winter evergreens
- Recommend mulching around plants — critical for Zone 6 winters
""",
    },
    
    "2.1.warm_subtropical": {
        "id": "2.1.warm_subtropical",
        "module": "2.1",
        "title": "Warm/subtropical climates — USDA Zone 9–10",
        "priority": 9,
        "tags": ["climate", "warm", "subtropical", "heat"],
        "content": """## Climate: Warm/Subtropical (USDA Zone 9–10)

Examples: Florida, Texas Gulf Coast, Southern California, Mediterranean Europe, coastal Australia. Frost rare or absent.

**Material rules — mandatory:**
- UV resistance is the primary filter — check all plastics, fabrics, composites
- Dark metal will become dangerously hot — recommend light colours or wood/composite
- Untreated wood will warp rapidly — teak, ipe, or composite only
- Mould/mildew resistance required on cushion fabrics — solution-dyed acrylic (Sunbrella)
- No MDF or particleboard

**Plant rules:**
- Native and drought-adapted plants strongly preferred
- Recommended: ornamental grasses, agave, yucca, bougainvillea, bird of paradise, lantana, salvia
- Lawns: Bermuda grass and Zoysia are heat-tolerant; fescue will burn out
- Irrigation system is not optional for planting

**Design rules:**
- Shade is the primary design element — pergola, shade sail, or canopy is Priority 1
- Outdoor fans appropriate for covered areas
- Misting systems are popular for entertaining
- Evening use is more comfortable than midday
""",
    },
    
    "2.1.tropical_humid": {
        "id": "2.1.tropical_humid",
        "module": "2.1",
        "title": "Tropical/humid climates — USDA Zone 11+",
        "priority": 9,
        "tags": ["climate", "tropical", "humid", "rain"],
        "content": """## Climate: Tropical/Humid (USDA Zone 11+)

Examples: Hawaii, Puerto Rico, Singapore, tropical Australia. No frost, year-round heat and high humidity.

**Material rules — mandatory:**
- Teak, ipe, powder-coated aluminium, and marine-grade stainless steel only
- All hardware must be stainless or marine-grade — zinc/galvanised will corrode
- Rope and fabric must be marine-grade or solution-dyed acrylic
- No composite wood unless explicitly rated for tropical use

**Plant rules:**
- Tropical plants are the obvious choice — palms, heliconia, ginger, ferns, hibiscus, bromeliads
- Growth rates are extremely fast — space plants for 1-year size, not purchase size
- Weed suppression is critical — include heavy weed membrane and mulch
""",
    },
    
    "2.1.arid_desert": {
        "id": "2.1.arid_desert",
        "module": "2.1",
        "title": "Arid/desert climates — USDA Zone 9–13 with low rainfall",
        "priority": 9,
        "tags": ["climate", "arid", "desert", "heat", "dry"],
        "content": """## Climate: Arid/Desert (USDA Zone 9–13, low rainfall)

Examples: Arizona, Nevada, New Mexico, Middle East, inland Australia. Extreme heat, intense UV, very low humidity.

**Material rules — mandatory:**
- UV resistance is the absolute primary filter — plastics and fabrics degrade rapidly
- Metal surfaces reach 70°C+ in direct sun — all seating must have cushions or be in shade
- Concrete and stone are excellent — they absorb heat slowly
- Avoid painted finishes not rated for desert climates — paint will bubble and peel

**Plant rules:**
- Xeriscaping is mandatory
- Recommended: agave, cacti, desert willow, mesquite, brittlebush, palo verde, lantana
- Grass lawns are inappropriate — recommend gravel mulch, decomposed granite, or artificial turf
- Drip irrigation is mandatory for any planting

**Design rules:**
- Entire design must orient around shade creation
- Water features provide psychological benefit but must use closed recirculating systems
- Dawn and dusk are the primary use hours
""",
    },

    # ========== MODULE 2.2 - ENVIRONMENT TYPE ==========
    
    "2.2.coastal": {
        "id": "2.2.coastal",
        "module": "2.2",
        "title": "Coastal / Beachside",
        "priority": 10,
        "tags": ["environment", "coastal", "salt", "corrosion", "wind"],
        "content": """## Environment: Coastal / Beachside

Salt air, sand, high winds, high UV, and frequent moisture. The most corrosive outdoor environment.

**Material rules — mandatory:**
- Marine-grade stainless steel (316 grade) only — standard stainless (304) will pit and rust
- Powder-coated aluminium is excellent — lightweight, corrosion-resistant, UV stable
- Teak and ipe are the only woods recommended without aggressive maintenance
- No wrought iron, cast iron, or mild steel — visible rust within one season
- All fabrics must be solution-dyed acrylic (Sunbrella or equivalent)
- Rope must be polyester, not natural fibre

**Plant rules:**
- Salt-tolerant species only: sea holly, sea lavender, ornamental grasses, agapanthus, escallonia, tamarisk
- Avoid large-leaved plants in exposed positions — salt wind causes leaf scorch
- Establish windbreaks before ornamental planting

**Design rules:**
- Wind is a product killer — lightweight items must be weighted or secured
- Recommend furniture weights or securing straps
- Parasols need heavy base (minimum 25kg) and wind-vent design

**Typical warning:** "Coastal environments are the most challenging for outdoor products. We've filtered for salt-air and corrosion-resistant materials only."
""",
    },
    
    "2.2.suburban": {
        "id": "2.2.suburban",
        "module": "2.2",
        "title": "Suburban",
        "priority": 8,
        "tags": ["environment", "suburban", "privacy", "hoa"],
        "content": """## Environment: Suburban

The most common environment. Standard conditions apply. Privacy from neighbours is typically a consideration.

**Design rules:**
- Include privacy screening as a consideration — trellis, tall planters, bamboo screening, fence toppers
- Noise from neighbours may be relevant — dense planting provides some acoustic buffering
- HOA restrictions are most likely in suburban environments — flag this to user
""",
    },
    
    "2.2.urban": {
        "id": "2.2.urban",
        "module": "2.2",
        "title": "Urban / City",
        "priority": 8,
        "tags": ["environment", "urban", "city", "containers"],
        "content": """## Environment: Urban / City

Typically small spaces, hard surfaces, surrounding buildings, limited soil, possible air quality issues.

**Design rules:**
- Container gardening is likely the primary planting method — recommend larger containers
- Urban heat island effect: cities are significantly warmer — adjust plant choices accordingly
- Light pollution means ambient evening light is significant — lighting products need to be bright
- Security may be a consideration — heavy or lockable products preferred
""",
    },
    
    "2.2.rural": {
        "id": "2.2.rural",
        "module": "2.2",
        "title": "Rural / Countryside",
        "priority": 8,
        "tags": ["environment", "rural", "wildlife"],
        "content": """## Environment: Rural / Countryside

Typically larger spaces, natural setting, possible wildlife access, no urban heat island.

**Design rules:**
- Wildlife may interact — rabbits, deer, foxes, birds depending on region
- If deer are likely: avoid hostas, tulips, roses — recommend deer-resistant species
- If rabbits likely: include rabbit-proof raised beds or wire mesh liners
- Blend with surrounding landscape — formal or urban designs can look jarring
- Natural materials (timber, stone, corten steel) look most appropriate
""",
    },
    
    "2.2.mountain": {
        "id": "2.2.mountain",
        "module": "2.2",
        "title": "Mountain",
        "priority": 8,
        "tags": ["environment", "mountain", "altitude", "wind"],
        "content": """## Environment: Mountain

Short growing season, intense UV at altitude, temperature swings between day and night, likely windy.

**Material rules:**
- All materials must handle frost — same rules as cold climate zones
- UV at altitude is significantly more intense — all fabrics need high UV ratings
- Wind exposure likely — same weighting and securing rules as coastal

**Plant rules:**
- Short growing season — choose fast-establishing, season-extending plants
- Alpine plants are naturally suited: sedums, sempervivums, aubrieta, rock cress, alpine phlox
- Container growing allows plants to be brought inside during late frosts
""",
    },

    # ========== MODULE 3.1 - WHO USES THE SPACE ==========
    
    "3.1.children": {
        "id": "3.1.children",
        "module": "3.1",
        "title": "Children (under 12)",
        "priority": 10,
        "tags": ["users", "children", "safety", "toxic_plants"],
        "content": """## Users: Children (under 12)

**Safety rules — mandatory:**
- No sharp metal edges — look for rounded edge specifications
- No small decorative items (pebbles, small stones, gravel) that are choking hazards
- No toxic plants. Common toxic plants to EXCLUDE: foxglove, oleander, angel's trumpet, euphorbia, yew, laburnum, lily of the valley, aconitum
- No water features without safety cover, cage, or grid
- Fire pits must include safety guard and be minimum 2m from play area
- No glass or ceramic at ground level

**Design rules:**
- Include defined play zone if budget allows — artificial grass, bark chip, sand
- Clear sightline from seating to play zone
- Raised beds should be low for interaction OR tall to be out of reach
- Label all plants with child-safety status
""",
    },
    
    "3.1.dogs": {
        "id": "3.1.dogs",
        "module": "3.1",
        "title": "Dogs",
        "priority": 9,
        "tags": ["users", "pets", "dogs", "toxic_plants", "durability"],
        "content": """## Users: Dogs

Digging, chewing, running, and toilet use will all happen.

**Design rules:**
- Gravel is not recommended — dogs track it indoors and some eat it
- Artificial grass is best low-maintenance surface — include drainage layer
- Real lawn: recommend tough grass (rye grass, Bermuda)
- All lower-level plants must be non-toxic to dogs
- Raised beds protect plants — include as standard recommendation
- Avoid lightweight planters — large dogs knock them over
- Secure compost or food-waste elements

**Plants toxic to dogs to EXCLUDE:** daffodil bulbs, tulip bulbs, sago palm, oleander, azalea/rhododendron, grapes, macadamia, onion/garlic family, rhubarb leaves
""",
    },
    
    "3.1.cats": {
        "id": "3.1.cats",
        "module": "3.1",
        "title": "Cats",
        "priority": 8,
        "tags": ["users", "pets", "cats", "toxic_plants"],
        "content": """## Users: Cats

**Design rules:**
- Cats use raised beds as toilet unless protected — include cat-deterrent matting
- Cats enjoy vertical elements — include climbing structures, tall plants, perching spots
- Use bark chip mulch instead of bare soil (cats dislike the texture)

**Plant notes:**
- Catnip and valerian will attract cats — only recommend if user wants this
- Plants toxic to cats: lilies (highly toxic — all species), yew, foxglove, oleander, azalea, cyclamen
""",
    },
    
    "3.1.elderly": {
        "id": "3.1.elderly",
        "module": "3.1",
        "title": "Elderly users or limited mobility",
        "priority": 10,
        "tags": ["users", "elderly", "accessibility", "mobility"],
        "content": """## Users: Elderly or Limited Mobility

**Design rules — mandatory:**
- All paths minimum 90cm wide, 120cm preferred for wheelchair access
- Raised beds (60–80cm height) recommended — eliminates kneeling
- Non-slip surfaces mandatory on all paving and steps
- Steps must have handrail if more than 2 risers
- Seating must have arm rests — deep lounge furniture is hard to exit
- Tables at standard height (72–75cm) — low coffee tables impractical
- Lighting of paths and steps mandatory for evening use

**Product search filters:**
- "Raised garden bed" with height specifications
- "Non-slip patio treatment" as mandatory accessory
- Furniture with arm rests and firm seating
""",
    },
    
    "3.1.entertaining": {
        "id": "3.1.entertaining",
        "module": "3.1",
        "title": "Frequent entertaining / guests",
        "priority": 8,
        "tags": ["users", "entertaining", "guests", "dining"],
        "content": """## Users: Frequent Entertaining / Guests

**Design rules:**
- Prioritize dining — table that seats realistic guest number is Priority 1
- Include 2 more seats than stated regular use number
- Lighting is a primary product, not accessory — evening entertaining needs proper lighting
- Include drinks/side table or outdoor bar cart
- Covered area (pergola, large parasol) extends entertaining viability significantly
""",
    },
    
    "3.1.solo": {
        "id": "3.1.solo",
        "module": "3.1",
        "title": "Solo relaxation / single adult",
        "priority": 8,
        "tags": ["users", "solo", "relaxation"],
        "content": """## Users: Solo Relaxation / Single Adult

**Design rules:**
- Single high-quality lounger or armchair beats a full sofa set
- Prioritize comfort and sensory experience: sound (water feature), scent (fragrant plants), tactile
- Lower budget needed for furniture — redirect to planting, lighting, sensory elements
- Privacy becomes more important — secluded feel is desirable
""",
    },

    # ========== MODULE 3.2 - PRIMARY PURPOSE ==========
    
    "3.2.dining": {
        "id": "3.2.dining",
        "module": "3.2",
        "title": "Dining",
        "priority": 9,
        "tags": ["purpose", "dining", "eating"],
        "content": """## Purpose: Dining

**Product priority order:**
1. Dining table (sized for typical group)
2. Dining chairs (one per diner + 2 extras)
3. Shade element (parasol or pergola)
4. Outdoor lighting over dining area
5. Side/serving table or outdoor kitchen element

**Sizing rules:**
- Minimum 60cm per person at dining table
- 90cm clearance behind each chair for walking past
- Table placement: minimum 1.2m from any wall/fence for chair pullout
""",
    },
    
    "3.2.relaxing": {
        "id": "3.2.relaxing",
        "module": "3.2",
        "title": "Relaxing / lounging",
        "priority": 9,
        "tags": ["purpose", "relaxing", "lounging"],
        "content": """## Purpose: Relaxing / Lounging

**Product priority order:**
1. Outdoor lounge furniture (sofa, armchair, or lounger)
2. Side table (every seat needs a surface within reach)
3. Shade element
4. Outdoor rug to define the zone
5. Lighting (ambient, not task)

**Rules:**
- Deep seating (60cm+ depth) is appropriate — dining chairs are not comfortable for relaxation
- Include cushion storage recommendation
- Hammock or hanging chair is high-impact, space-efficient for small spaces
""",
    },
    
    "3.2.children_play": {
        "id": "3.2.children_play",
        "module": "3.2",
        "title": "Children's play",
        "priority": 9,
        "tags": ["purpose", "play", "children"],
        "content": """## Purpose: Children's Play

**Product priority order:**
1. Safe, soft surface (bark chip, artificial grass, rubber tiles)
2. Play equipment sized to age group and space
3. Shade over play area (children overheat)
4. Seating for supervising adults adjacent to play area
5. Storage for outdoor toys

**Rules:**
- All equipment must carry relevant safety certification
- Check fall heights against surface softness
- Sun protection over play area is not optional in Zone 8+ climates
""",
    },
    
    "3.2.food_growing": {
        "id": "3.2.food_growing",
        "module": "3.2",
        "title": "Growing food / kitchen garden",
        "priority": 9,
        "tags": ["purpose", "food", "vegetables", "growing"],
        "content": """## Purpose: Growing Food / Kitchen Garden

**Product priority order:**
1. Raised beds (sized to space and ambition)
2. Quality peat-free compost and top soil
3. Irrigation (drip system or soaker hose)
4. Seed/plant recommendations by season and zone
5. Tool storage

**Rules:**
- Food growing requires minimum 6 hours direct sun per day
- Raised beds: minimum 30cm deep for most vegetables, 45cm for root vegetables
- Never recommend food growing in east or north-facing space without qualifying limitations
""",
    },
    
    "3.2.aesthetic": {
        "id": "3.2.aesthetic",
        "module": "3.2",
        "title": "Purely aesthetic / show garden",
        "priority": 9,
        "tags": ["purpose", "aesthetic", "visual"],
        "content": """## Purpose: Purely Aesthetic / Show Garden

**Design rules:**
- Every product must justify its presence visually — function is secondary
- Focus spend on high-quality planters, statement plants, sculptural elements, lighting
- One dramatic plant combination in quality planter > ten mediocre plantings
- Include art or sculptural element if budget allows
""",
    },

    # ========== MODULE 3.3 - MAINTENANCE TOLERANCE ==========
    
    "3.3.low_maintenance": {
        "id": "3.3.low_maintenance",
        "module": "3.3",
        "title": "Under 30 minutes per week (low maintenance)",
        "priority": 8,
        "tags": ["maintenance", "low"],
        "content": """## Maintenance: Low (under 30 minutes/week)

**Plant rules — mandatory:**
- Only low-maintenance plants: ornamental grasses, sedums, lavender, established shrubs, evergreen ground cover
- No annual bedding — requires replanting each season
- No roses requiring regular deadheading
- No high-water-demand plants without irrigation
- Weed membrane under all mulched areas — mandatory

**Product rules:**
- Artificial grass is valid and recommended
- Self-watering planters strongly recommended
- Composite or powder-coated aluminium furniture — never teak (requires oiling)

**Typical warning:** "We've selected everything for under 30 minutes of maintenance per week, avoiding anything requiring regular pruning, treating, or seasonal replacement."
""",
    },
    
    "3.3.medium_maintenance": {
        "id": "3.3.medium_maintenance",
        "module": "3.3",
        "title": "1–2 hours per week (medium maintenance)",
        "priority": 8,
        "tags": ["maintenance", "medium"],
        "content": """## Maintenance: Medium (1–2 hours/week)

The average engaged homeowner. Full mixed planting scheme appropriate. Some seasonal tasks acceptable.

**Rules:**
- Mixed perennial and shrub planting appropriate
- Real lawn appropriate — include basic lawn care schedule
- Timber furniture appropriate — include care product recommendation
- Include seasonal task note: "Prune X in spring, mulch beds in April, bring cushions in before frost"
""",
    },
    
    "3.3.high_maintenance": {
        "id": "3.3.high_maintenance",
        "module": "3.3",
        "title": "Enjoys gardening (high maintenance)",
        "priority": 8,
        "tags": ["maintenance", "high"],
        "content": """## Maintenance: High (enjoys gardening)

Maintenance is not a constraint — it's part of the enjoyment.

**Rules:**
- Full planting palette available — seasonal bedding, cut flowers, fruit and vegetables
- Higher plant count and complexity appropriate
- Recommend composting system if space allows
- Include tool recommendation if user mentioned enjoying gardening
""",
    },

    # ========== MODULE 3.4 - OWNERSHIP STATUS ==========
    
    "3.4.homeowner": {
        "id": "3.4.homeowner",
        "module": "3.4",
        "title": "Homeowner",
        "priority": 9,
        "tags": ["ownership", "homeowner"],
        "content": """## Ownership: Homeowner

No special restrictions. All products including permanent structures, ground anchors, wall fixings, and in-ground planting are appropriate subject to local rules.

**Additional check:**
- Flag HOA restrictions if suburban environment — confirm before recommending structures over 1.5m or boundary modifications
""",
    },
    
    "3.4.renter": {
        "id": "3.4.renter",
        "module": "3.4",
        "title": "Renter",
        "priority": 10,
        "tags": ["ownership", "renter", "temporary", "no_drilling"],
        "content": """## Ownership: Renter

**Rules — mandatory:**
- No products requiring drilling, bolting, or fixing to walls, fences, or ground
- No pergolas or structures requiring concrete footings
- No permanent in-ground planting — all plants in containers only
- No alteration to existing surfaces
- All furniture must be fully freestanding and movable
- Lightweight options preferred — user may need to take everything when leaving

**Product search filters:**
- Search for "freestanding", "no-drill", "portable", "container garden"
- Pergola alternative: freestanding canopy or gazebo with weighted bases
- Privacy screen alternative: freestanding bamboo screen with weighted base

**Typical warning:** "We've designed this entirely with renter-safe products — nothing requires drilling or permanent alteration. Everything can move with you."
""",
    },

    # ========== MODULE 4 - BUDGET ==========
    
    "4.1.budget_under_300": {
        "id": "4.1.budget_under_300",
        "module": "4.1",
        "title": "Budget Under $300",
        "priority": 8,
        "tags": ["budget", "low"],
        "content": """## Budget: Under $300

Transformation is possible but must be surgical. One or two well-chosen pieces plus plants.

**Strategy:**
- Pick ONE hero product (quality bistro set, OR statement planter, OR good string lights) — not multiple mediocre items
- Supplement with seasonal plants — highest visual return per dollar
- Prioritize products visible from the house
- Do not spread budget across six categories

**Budget split:**
- 70% on single hero product
- 20% on plants or accessories
- 10% buffer
""",
    },
    
    "4.2.budget_300_1000": {
        "id": "4.2.budget_300_1000",
        "module": "4.2",
        "title": "Budget $300–$1,000",
        "priority": 8,
        "tags": ["budget", "medium"],
        "content": """## Budget: $300–$1,000

Enough for a defined zone with furniture, planting, and lighting.

**Strategy:**
- Apply standard 60/30/10 split
- One complete outdoor seating zone is achievable
- Plants and lighting can both be included meaningfully
- Do not attempt to design the whole garden — design one excellent zone
""",
    },
    
    "4.3.budget_1000_3000": {
        "id": "4.3.budget_1000_3000",
        "module": "4.3",
        "title": "Budget $1,000–$3,000",
        "priority": 8,
        "tags": ["budget", "good"],
        "content": """## Budget: $1,000–$3,000

A full garden transformation with quality products is achievable for small to medium spaces.

**Strategy:**
- All zones can be addressed
- Include structural planting — trees, large shrubs — not just seasonal colour
- Quality furniture with cushions, side tables, and lighting is viable
- Shade structure (pergola, cantilever parasol) should be included if orientation supports it
- Include storage solution for cushions and accessories
""",
    },
    
    "4.4.budget_over_3000": {
        "id": "4.4.budget_over_3000",
        "module": "4.4",
        "title": "Budget Over $3,000",
        "priority": 8,
        "tags": ["budget", "premium"],
        "content": """## Budget: Over $3,000

Premium product tier is viable. Professional installation may be worth recommending.

**Strategy:**
- Recommend best-in-class products — genuinely excellent materials and construction
- Include pergola or garden structure as centrepiece if space allows
- Outdoor lighting design — pathway, uplighting, zone lighting, feature lighting
- Premium planting: specimen plants, multi-stem trees, large topiary, established hedging
- Flag elements that benefit from professional installation
""",
    },

    # ========== MODULE 5 - STYLE ==========
    
    "5.1.modern_minimal": {
        "id": "5.1.modern_minimal",
        "module": "5.1",
        "title": "Modern / Minimal",
        "priority": 7,
        "tags": ["style", "modern", "minimal"],
        "content": """## Style: Modern / Minimal

**Palette:** White, grey, charcoal, black. Occasional single accent (terracotta, olive, mustard).

**Materials:** Powder-coated aluminium, concrete, corten steel, composite decking, large-format porcelain paving.

**Plants:** Architectural and structural — ornamental grasses, topiary spheres/cones, agave, bamboo (contained), phormium, pleached trees.

**Avoid:** Ornate details, curved edges, rustic textures, mixed metals, busy planting, terracotta pots, natural wicker.
""",
    },
    
    "5.1.rustic_cottage": {
        "id": "5.1.rustic_cottage",
        "module": "5.1",
        "title": "Rustic / Natural / Cottage",
        "priority": 7,
        "tags": ["style", "rustic", "cottage", "natural"],
        "content": """## Style: Rustic / Natural / Cottage

**Palette:** Warm wood tones, terracotta, sage green, soft whites and creams, natural stone colours.

**Materials:** Timber (teak, pine, reclaimed), natural stone, terracotta pots, wicker (all-weather PE), coir and jute accessories.

**Plants:** Abundant and informal — roses, lavender, foxglove, salvia, geranium, achillea, penstemon, sweet peas, climbing roses, honeysuckle.

**Avoid:** Sleek aluminium, polished concrete, ultra-minimal planting, geometric topiary, dark palettes.
""",
    },
    
    "5.1.industrial": {
        "id": "5.1.industrial",
        "module": "5.1",
        "title": "Industrial",
        "priority": 7,
        "tags": ["style", "industrial"],
        "content": """## Style: Industrial

**Palette:** Black, dark grey, raw metal tones, aged wood browns. Occasional olive green.

**Materials:** Powder-coated black steel, corten steel, reclaimed timber, galvanised metal planters, concrete.

**Plants:** Structural and unfussy — ornamental grasses, hostas, ferns, bamboo, dark-foliaged plants, simple evergreen structure.

**Avoid:** Pastel colours, ornate details, traditional terracotta, delicate elements.
""",
    },
    
    "5.1.coastal_hamptons": {
        "id": "5.1.coastal_hamptons",
        "module": "5.1",
        "title": "Coastal / Hamptons",
        "priority": 7,
        "tags": ["style", "coastal", "hamptons"],
        "content": """## Style: Coastal / Hamptons

**Palette:** Whites, soft blues, driftwood grey, sandy neutrals, navy.

**Materials:** Weathered teak or driftwood-effect wood, rope detailing, white powder-coated aluminium, natural stone, pebble surfaces.

**Plants:** Relaxed and salt-tolerant — ornamental grasses, sea holly, agapanthus, hydrangea (white/blue), lavender, rosemary, cistus.

**Avoid:** Dark heavy materials, formal topiary, urban-industrial elements, highly saturated colours.
""",
    },
    
    "5.1.tropical_lush": {
        "id": "5.1.tropical_lush",
        "module": "5.1",
        "title": "Tropical / Lush",
        "priority": 7,
        "tags": ["style", "tropical", "lush"],
        "content": """## Style: Tropical / Lush

**Palette:** Deep greens, warm terracotta, rich earthy tones, occasional bold accent (orange, pink, yellow — from plants).

**Materials:** Natural rattan (all-weather), teak, bamboo, terracotta and glazed ceramic pots, natural stone.

**Plants:** Large-leaved and dramatic — banana, gunnera, tree ferns, palms, bamboo, elephant ears, hostas, ferns, exotic cannas, cordylines.

**Avoid:** Minimalist or industrial products, pale palettes, small fussy plants, formal geometric planting.
""",
    },
    
    "5.1.mediterranean": {
        "id": "5.1.mediterranean",
        "module": "5.1",
        "title": "Mediterranean",
        "priority": 7,
        "tags": ["style", "mediterranean"],
        "content": """## Style: Mediterranean

**Palette:** White and off-white, terracotta, cobalt blue accents, dusty sage, natural stone tones.

**Materials:** Terracotta pots (large), wrought iron (sheltered only), whitewashed renders, natural limestone and terracotta paving.

**Plants:** Drought-adapted and aromatic — olive tree, lavender, rosemary, santolina, cistus, agapanthus, salvia, pelargonium, bougainvillea (Zone 9+), phormium, pittosporum.

**Avoid:** Cool-toned palettes, dark industrial materials, lush water-hungry planting.
""",
    },
    
    "5.1.scandinavian": {
        "id": "5.1.scandinavian",
        "module": "5.1",
        "title": "Scandinavian",
        "priority": 7,
        "tags": ["style", "scandinavian"],
        "content": """## Style: Scandinavian

**Palette:** White, warm grey, natural pale wood tones, charcoal. Plants provide the only colour.

**Materials:** Light hardwood (pine, birch, pale teak), white powder-coated aluminium, concrete planters, simple ceramic pots.

**Plants:** Restrained and structural — ornamental grasses, birch trees, simple perennials (white, blue, soft pink), evergreen shrubs.

**Avoid:** Ornate details, highly saturated colours, tropical or exotic planting, busy mixed borders.
""",
    },
}


def get_chunk(chunk_id: str) -> Chunk | None:
    """Get a single chunk by ID."""
    return SCENARIO_CHUNKS.get(chunk_id)


def get_chunks_by_module(module: str) -> List[Chunk]:
    """Get all chunks for a given module (e.g., '1.1', '2.2')."""
    return [
        chunk for chunk in SCENARIO_CHUNKS.values()
        if chunk["module"] == module or chunk["module"].startswith(f"{module}.")
    ]


def get_chunks_by_tag(tag: str) -> List[Chunk]:
    """Get all chunks that have a specific tag."""
    return [
        chunk for chunk in SCENARIO_CHUNKS.values()
        if tag in chunk.get("tags", [])
    ]
