"""
Room upgrade router.
Coordinates photo analysis, product search, budget optimization, and image generation.
Uses multi-image fusion to place actual product images into the scene.
"""
import asyncio
import base64
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Body, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse

from ..models.schemas import (
    RoomUpgradeAnalyzeRequest,
    RoomUpgradeAnalyzeResponse,
    RoomUpgradeGenerateRequest,
    RoomUpgradeGenerateResponse,
    RoomUpgradeSearchRequest,
    SelectedProduct,
    YardUpgradeAnalyzeResponse,
    YardDesignAdvice,
    SpaceAssessment,
    DesignApproach,
    DesignConstraint,
    ActionStep,
    ProductRequirement,
    DesignWarning,
    SeasonalNotes,
    CityContext,
)
from ..services.budget_optimizer_service import budget_optimizer_service
from ..services.gemini_service import gemini_service
from ..services.product_search_service import product_search_service
from ..services.scene_analysis_service import scene_analysis_service
from ..services.yard_advisor_service import yard_advisor_service
from ..services.scenario_context_service import YardInputs
from ..services.location_intelligence_service import location_intelligence_service
from ..services.plant_spec_service import plant_spec_service
from ..services.plant_image_service import plant_image_service
from ..data.chunk_index import get_climate_override_chunks
from ..utils.dimensions import (
    compute_area_sqm,
    format_area,
    format_yard_dimensions,
    normalize_dimensions_string,
)

router = APIRouter(prefix="/room-upgrade", tags=["Room Upgrade"])


@router.get("/runner", response_class=HTMLResponse)
async def room_upgrade_runner():
    """
    Tiny local-only runner for testing the full room-upgrade pipeline.
    No database, no mobile app, no build step.
    """
    return HTMLResponse(
        """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Room Upgrade Runner</title>
  <link rel="stylesheet" href="/static/css/runner.css" />
</head>
<body>
  <main>
    <h1>Room Upgrade Runner</h1>
    <p>Upload a photo and prompt. The backend infers the budget, finds products, generates an after image, and shows product links.</p>

    <form id="runnerForm" class="card">
      <label for="image">Photo</label>
      <input id="image" name="image" type="file" accept="image/*" required />
      <br /><br />
      <label for="prompt">Prompt</label>
      <textarea id="prompt" name="prompt" placeholder="Optional. Example: I have 3 kids and a dog. We hang out in summer evenings. Make this yard better."></textarea>
      <br /><br />
      <details>
        <summary><strong>Advanced yard inputs</strong> <span class="muted">(optional - improves advisor reasoning)</span></summary>
        <br />
        <div class="fields">
          <div class="field">
            <label for="budget">Budget</label>
            <input id="budget" name="budget" type="number" min="0" step="1" placeholder="500" />
          </div>
          <div class="field">
            <label for="unit_system">Units</label>
            <select id="unit_system" name="unit_system">
              <option value="metric" selected>Metric (m / cm)</option>
              <option value="imperial">Imperial (ft / in)</option>
            </select>
          </div>
          <div class="field">
            <label for="yard_length">Yard length</label>
            <input id="yard_length" name="yard_length" type="number" min="0" step="0.1" placeholder="5" />
          </div>
          <div class="field">
            <label for="yard_width">Yard width</label>
            <input id="yard_width" name="yard_width" type="number" min="0" step="0.1" placeholder="5" />
          </div>
          <div class="field">
            <label for="city_or_region">City / region</label>
            <input id="city_or_region" name="city_or_region" placeholder="Miami" />
          </div>
          <div class="field">
            <label for="orientation">Orientation</label>
            <select id="orientation" name="orientation">
              <option value="">Not sure</option>
              <option value="north">North</option>
              <option value="south">South</option>
              <option value="east">East</option>
              <option value="west">West</option>
            </select>
          </div>
          <div class="field">
            <label for="surface_type">Surface</label>
            <select id="surface_type" name="surface_type">
              <option value="">Not sure</option>
              <option value="grass">Grass</option>
              <option value="concrete">Concrete / paving</option>
              <option value="gravel">Gravel</option>
              <option value="decking">Decking</option>
              <option value="bare_soil">Bare soil</option>
              <option value="mixed">Mixed</option>
            </select>
          </div>
          <div class="field">
            <label for="slope">Slope</label>
            <select id="slope" name="slope">
              <option value="">Not sure</option>
              <option value="flat">Flat</option>
              <option value="gentle">Gentle</option>
              <option value="significant">Significant</option>
            </select>
          </div>
          <div class="field">
            <label for="setting">Setting</label>
            <select id="setting" name="setting">
              <option value="">Not sure</option>
              <option value="coastal_exposed">Coastal / exposed</option>
              <option value="suburban">Suburban</option>
              <option value="urban">Urban / city</option>
              <option value="rural">Rural / countryside</option>
              <option value="mountain">Mountain / high altitude</option>
            </select>
          </div>
          <div class="field">
            <label for="primary_purpose">Primary purpose</label>
            <select id="primary_purpose" name="primary_purpose">
              <option value="">Not sure</option>
              <option value="dining">Dining</option>
              <option value="relaxing">Relaxing</option>
              <option value="children_play">Children play</option>
              <option value="food_growing">Food growing</option>
              <option value="aesthetic">Aesthetic</option>
            </select>
          </div>
          <div class="field">
            <label for="maintenance">Maintenance</label>
            <select id="maintenance" name="maintenance">
              <option value="">Not sure</option>
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
            </select>
          </div>
          <div class="field">
            <label for="style_preference">Style</label>
            <select id="style_preference" name="style_preference">
              <option value="">Not sure</option>
              <option value="modern">Modern</option>
              <option value="rustic">Rustic / cottage</option>
              <option value="coastal">Coastal</option>
              <option value="tropical">Tropical</option>
              <option value="mediterranean">Mediterranean</option>
              <option value="scandinavian">Scandinavian</option>
              <option value="industrial">Industrial</option>
            </select>
          </div>
          <div class="field">
            <label for="ownership">Ownership</label>
            <select id="ownership" name="ownership">
              <option value="">Not sure</option>
              <option value="owner">Owner</option>
              <option value="renter">Renter</option>
            </select>
          </div>
        </div>
        <br />
        <label>Who uses this space?</label>
        <div class="checks">
          <label><input type="checkbox" name="who_uses" value="adults" /> Adults</label>
          <label><input type="checkbox" name="who_uses" value="children" /> Children</label>
          <label><input type="checkbox" name="who_uses" value="dogs" /> Dogs</label>
          <label><input type="checkbox" name="who_uses" value="cats" /> Cats</label>
          <label><input type="checkbox" name="who_uses" value="elderly" /> Elderly / mobility needs</label>
          <label><input type="checkbox" name="who_uses" value="entertaining" /> Guests / entertaining</label>
        </div>
      </details>
      <button id="runButton" type="submit">Run full pipeline</button>
      <p id="status" class="muted"></p>
    </form>

    <section id="results" class="hidden">
      <div class="card">
        <h2>Images</h2>
        <div class="grid">
          <div>
            <h3>Before</h3>
            <img id="beforeImage" alt="Before image" />
          </div>
          <div>
            <h3>After</h3>
            <img id="afterImage" alt="After image" />
          </div>
        </div>
      </div>

      <div class="card">
        <h2>Budget</h2>
        <p id="budgetSummary"></p>
      </div>

      <div id="adviceCard" class="card hidden">
        <h2>Designer Advice</h2>
        <div id="advice"></div>
      </div>

      <div id="locationCard" class="card location-card hidden">
        <h2>Location Profile</h2>
        <div id="locationProfile" class="location-grid">
          <div class="location-section">
            <div class="location-hero">
              <span class="location-city" id="loc-city">-</span>
              <span class="location-country" id="loc-country">-</span>
            </div>
            <div class="location-tags" id="loc-tags"></div>
          </div>
          <div class="location-stats" id="loc-stats"></div>
          <div class="location-summaries" id="loc-summaries"></div>
        </div>
      </div>

      <div id="plantSpecCard" class="card plant-spec-card hidden">
        <h2>Plant Specification</h2>
        <div id="plantSpec" class="plant-list"></div>
      </div>

      <div class="card">
        <h2>Products</h2>
        <div id="products"></div>
      </div>

      <div class="card">
        <h2>Generated Prompt</h2>
        <pre id="generatedPrompt"></pre>
      </div>
    </section>
  </main>

  <script src="/static/js/runner.js"></script>
</body>
</html>
        """
    )


@router.post("/analyze", response_model=RoomUpgradeAnalyzeResponse)
async def analyze_room_upgrade(request: RoomUpgradeAnalyzeRequest):
    """
    Full preparation flow: analyze the uploaded space, search products,
    and select a product combination that fits the user's budget.
    """
    try:
        budget = request.budget
        if budget is None or budget <= 0:
            budget = await scene_analysis_service.infer_budget(
                image_base64=request.image_base64,
                prompt=request.prompt,
                currency=request.currency,
            )
        if budget is None or budget <= 0:
            raise HTTPException(status_code=400, detail="Could not infer a valid budget.")

        scene_analysis = await scene_analysis_service.analyze_scene(
            image_base64=request.image_base64,
            prompt=request.prompt,
            budget=budget,
            currency=request.currency,
        )

        search_results = await asyncio.gather(
            *[
                product_search_service.search_with_fallback(item)
                for item in scene_analysis.shopping_list
            ]
        )
        search_results = [
            result for result in search_results if result.all_candidates
        ]

        selected_products, total, within_budget = await budget_optimizer_service.optimize(
            search_results,
            budget,
        )
        selected_products = await product_search_service.resolve_selected_product_links(
            selected_products
        )

        return RoomUpgradeAnalyzeResponse(
            scene_analysis=scene_analysis,
            search_results=search_results,
            selected_products=selected_products,
            total_estimated=total,
            within_budget=within_budget,
            budget=budget,
            currency=request.currency,
        )
    except HTTPException:
        raise
    except Exception as exc:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/analyze/upload", response_model=YardUpgradeAnalyzeResponse)
async def analyze_room_upgrade_upload(
    prompt: str = Form(""),
    budget: Optional[float] = Form(None),
    currency: str = Form("USD"),
    image: UploadFile = File(...),
    # Optional yard design inputs
    unit_system: Optional[str] = Form(None),
    yard_length: Optional[float] = Form(None),
    yard_width: Optional[float] = Form(None),
    dimensions_sqm: Optional[float] = Form(None),
    orientation: Optional[str] = Form(None),
    surface_type: Optional[str] = Form(None),
    slope: Optional[str] = Form(None),
    city_or_region: Optional[str] = Form(None),
    city_context: Optional[str] = Form(None),
    environment_type: Optional[str] = Form(None),
    primary_purpose: Optional[str] = Form(None),
    who_uses: Optional[str] = Form(None),  # Comma-separated list
    maintenance: Optional[str] = Form(None),
    style_preference: Optional[str] = Form(None),
    ownership: Optional[str] = Form(None),
):
    """
    Multipart convenience endpoint for mobile clients.
    Accepts optional yard design inputs for enhanced advice generation.
    """
    image_content = await image.read()
    image_base64 = base64.b64encode(image_content).decode("utf-8")
    
    # Parse who_uses from comma-separated string to list
    who_uses_list = None
    if who_uses:
        who_uses_list = [w.strip() for w in who_uses.split(",") if w.strip()]

    # Compute sqm from yard length×width (if provided)
    computed_sqm = None
    if yard_length is not None and yard_width is not None and yard_length > 0 and yard_width > 0:
        unit = (unit_system or "metric").strip().lower()
        if unit == "imperial":
            # Inputs are in feet; convert to meters
            length_m = float(yard_length) * 0.3048
            width_m = float(yard_width) * 0.3048
        else:
            # Default to metric meters
            length_m = float(yard_length)
            width_m = float(yard_width)
        computed_sqm = max(0.0, length_m * width_m)
        if dimensions_sqm is None:
            dimensions_sqm = computed_sqm
    
    # Build yard inputs if any were provided
    yard_inputs = YardInputs(
        unit_system=unit_system,
        yard_length=yard_length,
        yard_width=yard_width,
        dimensions_sqm=dimensions_sqm,
        orientation=orientation,
        surface_type=surface_type,
        slope=slope,
        city_or_region=city_or_region,
        city_context=city_context,
        environment_type=environment_type,
        primary_purpose=primary_purpose,
        who_uses=who_uses_list,
        maintenance=maintenance,
        style_preference=style_preference,
        ownership=ownership,
        budget=budget,
    )
    
    request = RoomUpgradeAnalyzeRequest(
        image_base64=image_base64,
        prompt=prompt,
        budget=budget,
        currency=currency,
    )
    return await analyze_room_upgrade_with_advice(request, yard_inputs)


async def analyze_room_upgrade_with_advice(
    request: RoomUpgradeAnalyzeRequest,
    yard_inputs: YardInputs,
) -> YardUpgradeAnalyzeResponse:
    """
    Full preparation flow with optional yard design advice.
    If yard inputs are provided, generates comprehensive design advice.
    """
    try:
        budget = request.budget
        if budget is None or budget <= 0:
            budget = await scene_analysis_service.infer_budget(
                image_base64=request.image_base64,
                prompt=request.prompt,
                currency=request.currency,
            )
        if budget is None or budget <= 0:
            raise HTTPException(status_code=400, detail="Could not infer a valid budget.")

        # Update yard_inputs budget if it was inferred
        if yard_inputs.budget is None:
            yard_inputs.budget = budget

        scene_analysis = await scene_analysis_service.analyze_scene(
            image_base64=request.image_base64,
            prompt=request.prompt,
            budget=budget,
            currency=request.currency,
        )

        design_advice = None
        location_profile_model = None
        plant_spec = None
        site_palette_text = None
        override_chunk_ids: Optional[List[str]] = None
        dynamic_chunks: Optional[List[Dict[str, Any]]] = None
        from ..services.scenario_context_service import scenario_context_service

        if scenario_context_service.has_inputs(yard_inputs):
            print("[Router] Yard inputs provided, generating design advice...")
            photo_analysis = (
                scene_analysis.model_dump()
                if hasattr(scene_analysis, "model_dump")
                else scene_analysis.dict()
            )
            location_profile_dict = None

            if yard_inputs.city_or_region:
                ctx = None
                if yard_inputs.city_context in {"coastal", "inland", "unknown"}:
                    try:
                        ctx = CityContext(yard_inputs.city_context)
                    except Exception:
                        ctx = None

                location_profile_model = await location_intelligence_service.get_location_profile(
                    city_or_region=yard_inputs.city_or_region,
                    city_context=ctx,
                )
                location_profile_dict = (
                    location_profile_model.model_dump()
                    if hasattr(location_profile_model, "model_dump")
                    else location_profile_model.dict()
                )
                # The override helper expects `solar_lighting_viable` but the profile schema uses
                # `solar_lighting_viability`. Provide the expected key for chunk lookups.
                if (
                    "solar_lighting_viable" not in location_profile_dict
                    and "solar_lighting_viability" in location_profile_dict
                ):
                    location_profile_dict["solar_lighting_viable"] = location_profile_dict.get(
                        "solar_lighting_viability"
                    )
                override_chunk_ids = get_climate_override_chunks(location_profile_dict)
                site_palette_text = location_intelligence_service.build_site_palette_text(
                    location_profile_model
                )
                dynamic_chunks = [
                    {
                        "id": "2.4.site_palette",
                        "module": "2.4",
                        "title": f"Site Plant Palette — {location_profile_model.city}",
                        "priority": 12,
                        "tags": ["plants", "palette", "location", "dynamic"],
                        "content": site_palette_text,
                    }
                ]

            advice_raw = await yard_advisor_service.generate_design_advice(
                yard_inputs,
                photo_analysis=photo_analysis,
                location_profile=location_profile_dict,
                site_palette=site_palette_text,
                override_chunk_ids=override_chunk_ids,
                dynamic_chunks=dynamic_chunks,
            )
            design_advice = _parse_advice_to_model(advice_raw)

            if design_advice is not None:
                _apply_advice_to_shopping_list(scene_analysis, design_advice)

            if (
                site_palette_text
                and (yard_inputs.style_preference or yard_inputs.primary_purpose)
                and location_profile_dict is not None
            ):
                user_inputs_dict: Dict[str, Any] = {
                    "city_or_region": yard_inputs.city_or_region,
                    "unit_system": yard_inputs.unit_system,
                    "yard_length": yard_inputs.yard_length,
                    "yard_width": yard_inputs.yard_width,
                    "dimensions_sqm": yard_inputs.dimensions_sqm,
                    "orientation": yard_inputs.orientation,
                    "surface_type": yard_inputs.surface_type,
                    "style_preference": yard_inputs.style_preference,
                    "primary_purpose": yard_inputs.primary_purpose,
                    "who_uses": yard_inputs.who_uses or [],
                    "maintenance": yard_inputs.maintenance,
                    "budget": yard_inputs.budget,
                    "allergies": "",
                    "pets": "",
                }
                plant_spec = await plant_spec_service.generate_plant_spec(
                    site_palette=site_palette_text,
                    user_inputs=user_inputs_dict,
                    location_profile=location_profile_dict,
                )

        search_results = await asyncio.gather(
            *[
                product_search_service.search_with_fallback(item)
                for item in scene_analysis.shopping_list
            ]
        )
        search_results = [
            result for result in search_results if result.all_candidates
        ]

        selected_products, total, within_budget = await budget_optimizer_service.optimize(
            search_results,
            budget,
        )
        selected_products = await product_search_service.resolve_selected_product_links(
            selected_products
        )

        # Normalize product dimensions to user's chosen unit system (for UI + Gemini prompt consistency)
        unit_system = (yard_inputs.unit_system or "metric").strip().lower()
        for selected in selected_products:
            product = selected.chosen_product
            product.dimensions = normalize_dimensions_string(
                product.dimensions,
                unit_system=unit_system,
                kind="product",
            )

        return YardUpgradeAnalyzeResponse(
            design_advice=design_advice,
            location_profile=location_profile_model,
            plant_spec=plant_spec,
            scene_analysis=scene_analysis,
            search_results=search_results,
            selected_products=selected_products,
            total_estimated=total,
            within_budget=within_budget,
            budget=budget,
            currency=request.currency,
        )
    except HTTPException:
        raise
    except Exception as exc:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc))


def _parse_advice_to_model(advice_raw: dict) -> Optional[YardDesignAdvice]:
    """Convert raw advice dictionary to Pydantic model."""
    if not advice_raw or advice_raw.get("_metadata", {}).get("note"):
        return None
    
    try:
        # Parse space_assessment
        space_assessment = None
        if advice_raw.get("space_assessment"):
            sa = advice_raw["space_assessment"]
            space_assessment = SpaceAssessment(
                summary=sa.get("summary", ""),
                size_category=sa.get("size_category"),
                key_characteristics=sa.get("key_characteristics", []),
            )
        
        # Parse design_approach
        design_approach = None
        if advice_raw.get("design_approach"):
            da = advice_raw["design_approach"]
            design_approach = DesignApproach(
                strategy=da.get("strategy", ""),
                reasoning=da.get("reasoning", ""),
                focal_point=da.get("focal_point"),
                zones=da.get("zones", []),
            )
        
        # Parse key_constraints
        key_constraints = []
        for c in advice_raw.get("key_constraints", []):
            key_constraints.append(DesignConstraint(
                title=c.get("title", ""),
                explanation=c.get("explanation", ""),
                impact=c.get("impact", ""),
                user_action=c.get("user_action", ""),
            ))
        
        # Parse action_plan
        action_plan = []
        for a in advice_raw.get("action_plan", []):
            action_plan.append(ActionStep(
                step=a.get("step", 0),
                action=a.get("action", ""),
                detail=a.get("detail", ""),
                reasoning=a.get("reasoning", ""),
            ))
        
        # Parse product_requirements
        product_requirements = []
        for p in advice_raw.get("product_requirements", []):
            product_requirements.append(ProductRequirement(
                category=p.get("category", ""),
                requirements=p.get("requirements", ""),
                search_terms=p.get("search_terms", []),
                budget_allocation=p.get("budget_allocation", 0),
                placement=p.get("placement", ""),
            ))
        
        # Parse warnings
        warnings = []
        for w in advice_raw.get("warnings", []):
            warnings.append(DesignWarning(
                severity=w.get("severity", "info"),
                title=w.get("title", ""),
                message=w.get("message", ""),
            ))
        
        # Parse seasonal_notes
        seasonal_notes = None
        if advice_raw.get("seasonal_notes"):
            sn = advice_raw["seasonal_notes"]
            seasonal_notes = SeasonalNotes(
                spring=sn.get("spring"),
                summer=sn.get("summer"),
                autumn=sn.get("autumn"),
                winter=sn.get("winter"),
            )
        
        return YardDesignAdvice(
            space_assessment=space_assessment,
            key_constraints=key_constraints,
            design_approach=design_approach,
            action_plan=action_plan,
            product_requirements=product_requirements,
            warnings=warnings,
            seasonal_notes=seasonal_notes,
        )
    except Exception as e:
        print(f"[Router] Error parsing advice: {e}")
        return None


def _apply_advice_to_shopping_list(scene_analysis, design_advice: YardDesignAdvice) -> None:
    """
    Enrich product search descriptions with advisor constraints.
    Keeps the original shopping list shape but nudges search toward materials,
    safety requirements, style, and placement guidance from the scenario rules.
    """
    if not design_advice.product_requirements:
        return

    for item in scene_analysis.shopping_list:
        item_text = f"{item.item_name} {item.search_description}".lower()
        matched_requirements = []

        for requirement in design_advice.product_requirements:
            category = requirement.category.lower()
            if category and category in item_text:
                matched_requirements.append(requirement)

        if not matched_requirements:
            matched_requirements = design_advice.product_requirements[:1]

        additions = []
        for requirement in matched_requirements:
            if requirement.requirements:
                additions.append(requirement.requirements)
            if requirement.search_terms:
                additions.append("Search terms: " + ", ".join(requirement.search_terms[:5]))

        if additions:
            item.search_description = (
                f"{item.search_description}. Yard advisor requirements: "
                + " ".join(additions)
            )


@router.post("/search-products", response_model=RoomUpgradeAnalyzeResponse)
async def search_products_for_upgrade(request: RoomUpgradeSearchRequest):
    """
    Search and optimize products for a shopping list without re-analyzing the image.
    """
    try:
        search_results = await asyncio.gather(
            *[
                product_search_service.search_with_fallback(item)
                for item in request.shopping_list
            ]
        )
        search_results = [
            result for result in search_results if result.all_candidates
        ]
        selected_products, total, within_budget = await budget_optimizer_service.optimize(
            search_results,
            request.budget,
        )
        selected_products = await product_search_service.resolve_selected_product_links(
            selected_products
        )

        return RoomUpgradeAnalyzeResponse(
            scene_analysis={
                "space_type": "space",
                "existing_items": [],
                "style_observation": "",
                "shopping_list": request.shopping_list,
            },
            search_results=search_results,
            selected_products=selected_products,
            total_estimated=total,
            within_budget=within_budget,
            budget=request.budget,
            currency=request.currency,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/plant-images")
async def get_plant_images(payload: Dict[str, Any] = Body(...)):
    """
    Batch plant image lookup endpoint.

    Expected request JSON:
      { "plants": [ { "key": "...", "botanical_name": "...", "common_name": "..." }, ... ] }

    Response:
      { "images": { "<key>": "<url or empty string>" } }
    """
    try:
        plants = (payload or {}).get("plants") if isinstance(payload, dict) else None
        if not isinstance(plants, list):
            raise HTTPException(status_code=400, detail="Invalid payload: expected {plants: []}.")

        results: Dict[str, str] = {}
        for item in plants[:30]:
            if not isinstance(item, dict):
                continue
            key = str(item.get("key") or "").strip()
            if not key:
                continue
            botanical = str(item.get("botanical_name") or "").strip()
            common = str(item.get("common_name") or "").strip()
            url = await plant_image_service.get_plant_image_url(
                botanical_name=botanical,
                common_name=common,
            )
            results[key] = url or ""

        return {"images": results}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/generate", response_model=RoomUpgradeGenerateResponse)
async def generate_room_upgrade(request: RoomUpgradeGenerateRequest):
    """
    Generate an after photo using the approved product list.
    Uses multi-image fusion: passes product reference images to Gemini
    so the actual products appear in the generated image.
    """
    try:
        image_base64 = _strip_data_url(request.image_base64)

        # Fetch product reference images for multi-image fusion
        print(f"Fetching {len(request.selected_products)} product images...")
        product_images = await fetch_product_images(request.selected_products)
        print(f"Successfully fetched {len(product_images)} product images")

        # Build prompt that references each product image by position
        prompt = build_room_upgrade_prompt_v2(request, len(product_images))

        # Use multi-image fusion if we have product images
        if product_images:
            generated_images = await gemini_service.edit_room_with_products(
                room_image_base64=image_base64,
                product_images=product_images,
                prompt=prompt,
            )
        else:
            # Fallback to text-only prompt
            print("No product images fetched, using text-only prompt")
            generated_images = await gemini_service.edit_room(
                image_base64=image_base64,
                edit_instruction=prompt,
                style="modern",
            )

        return RoomUpgradeGenerateResponse(
            after_image_url=generated_images[0] if generated_images else None,
            generated_images=generated_images,
            prompt_used=prompt,
        )
    except Exception as exc:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(exc))


async def fetch_product_images(
    selected_products: List[SelectedProduct],
    max_products: int = 6,
) -> List[bytes]:
    """
    Download product images for Gemini multi-image fusion.
    Returns list of image bytes, preserving order.
    """
    products_to_fetch = selected_products[:max_products]

    async def fetch_single(product: SelectedProduct) -> Optional[bytes]:
        # Prefer high-res image if available
        image_url = (
            product.chosen_product.high_res_image_url
            or product.chosen_product.image_url
        )
        if not image_url:
            return None

        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                response = await client.get(image_url)
                response.raise_for_status()
                content = response.content

                # Validate it's actually image data (check magic bytes)
                if content[:4] in (b'\xff\xd8\xff\xe0', b'\xff\xd8\xff\xe1',  # JPEG
                                   b'\x89PNG', b'RIFF', b'GIF8'):  # PNG, WebP, GIF
                    return content
                if content[:8].startswith(b'\x89PNG'):
                    return content

                # Accept if content-type says it's an image
                content_type = response.headers.get("content-type", "")
                if "image" in content_type:
                    return content

                print(f"Skipping non-image content from {image_url[:50]}...")
                return None

        except Exception as exc:
            print(f"Failed to fetch product image: {exc}")
            return None

    # Fetch all in parallel
    tasks = [fetch_single(product) for product in products_to_fetch]
    results = await asyncio.gather(*tasks)

    # Filter out None values while preserving corresponding product order
    return [img for img in results if img is not None]


def _extract_plant_names(plant_spec: Optional[str]) -> List[tuple]:
    """
    Parse plant_spec text and extract plant names.
    
    Returns list of tuples: [(botanical_name, common_name), ...]
    """
    if not plant_spec:
        return []
    
    import re
    plants = []
    
    # Find all botanical names and common names
    botanical_pattern = r"Botanical name:\s*(.+?)(?:\n|$)"
    common_pattern = r"Common name:\s*(.+?)(?:\n|$)"
    
    botanical_matches = re.findall(botanical_pattern, plant_spec, re.IGNORECASE)
    common_matches = re.findall(common_pattern, plant_spec, re.IGNORECASE)
    
    # Pair them up (they should appear in order)
    for i in range(max(len(botanical_matches), len(common_matches))):
        botanical = botanical_matches[i].strip() if i < len(botanical_matches) else ""
        common = common_matches[i].strip() if i < len(common_matches) else ""
        if botanical or common:
            plants.append((botanical, common))
    
    return plants


def build_room_upgrade_prompt_v2(
    request: RoomUpgradeGenerateRequest,
    num_product_images: int,
) -> str:
    """
    Build prompt that references product images by position.
    Image 1 = room photo, Images 2-N = product photos.
    """
    item_descriptions = []
    raw_unit_system = request.unit_system
    if raw_unit_system is None:
        unit_system = "metric"
    else:
        unit_system = str(getattr(raw_unit_system, "value", raw_unit_system)).strip().lower()

    yard_dims = format_yard_dimensions(
        yard_length=request.yard_length,
        yard_width=request.yard_width,
        unit_system=unit_system,
    )
    yard_area = format_area(
        area_sqm=compute_area_sqm(
            yard_length=request.yard_length,
            yard_width=request.yard_width,
            unit_system=unit_system,
        ),
        unit_system=unit_system,
    )
    space_dims_line = ""
    if yard_dims:
        space_dims_line = f"\nSpace dimensions: {yard_dims}"
        if yard_area:
            space_dims_line += f" (approx. {yard_area})"

    for index, selected in enumerate(request.selected_products, start=1):
        product = selected.chosen_product
        item = selected.shopping_list_item

        # Build detailed product description
        details = []
        if product.material:
            details.append(f"made of {product.material}")
        if product.color:
            details.append(f"in {product.color}")
        normalized_dims = normalize_dimensions_string(
            product.dimensions,
            unit_system=unit_system,
            kind="product",
        )
        if normalized_dims:
            details.append(f"size: {normalized_dims}")

        detail_str = f" ({', '.join(details)})" if details else ""

        # Reference the product image if available
        if index <= num_product_images:
            image_ref = f"[Use the EXACT product from Image {index + 1}]"
        else:
            image_ref = ""

        item_descriptions.append(
            f"{index}. {product.title}{detail_str}\n"
            f"   Store: {product.store}, Price: ${product.price:.2f}\n"
            f"   Placement: {item.placement}\n"
            f"   {image_ref}"
        )

    user_prompt = f"\nUser request: {request.prompt}" if request.prompt else ""

    # Extract and format plant names if plant_spec is provided
    plants = _extract_plant_names(getattr(request, 'plant_spec', None))
    plants_section = ""
    plants_rule = ""
    if plants:
        plant_lines = []
        for botanical, common in plants:
            if botanical and common:
                plant_lines.append(f"- {common} ({botanical})")
            elif common:
                plant_lines.append(f"- {common}")
            elif botanical:
                plant_lines.append(f"- {botanical}")
        if plant_lines:
            plants_section = "\n\nPlants to include in the garden design:\n" + "\n".join(plant_lines)
            plants_rule = "\n9. Include the specified plants naturally in appropriate locations - along borders, near seating areas, or as focal points"

    # If we have product images, use multi-image prompt
    if num_product_images > 0:
        return f"""You are editing Image 1 (the room/outdoor space photo).{user_prompt}{space_dims_line}

I am providing {num_product_images} product reference images (Images 2-{num_product_images + 1}).
You MUST add these EXACT products to the scene - use their appearance from the reference images.

Products to add:

{chr(10).join(item_descriptions)}{plants_section}

CRITICAL RULES:
1. DO NOT change the camera angle, perspective, or viewpoint - keep EXACTLY the same view as the original photo
2. Use the EXACT visual appearance of each product from its reference image
3. Products must be CLEARLY VISIBLE in the final image - not subtle or hidden
4. Match lighting and shadows to the room
5. Place products naturally but prominently where specified
6. Preserve EVERYTHING in the original photo - walls, floors, grass, plants, furniture, architecture
7. NO labels, watermarks, text overlays, or price tags
8. The output should look like the SAME photo with products added, not a new photo
9. NEVER place rugs, carpets, or mats on grass, soil, or natural ground - they only belong on hard surfaces (deck, patio, concrete){plants_rule}

The space is a {request.scene_analysis.space_type}.
Current style: {request.scene_analysis.style_observation}

Generate the edited image now. Keep the EXACT same photo, just add the products."""

    # Fallback text-only prompt (when no product images available)
    plants_rule_text = "\n- Include the specified plants naturally in appropriate locations - along borders, near seating areas, or as focal points" if plants else ""
    return f"""You are editing the provided room or outdoor space photo.{user_prompt}{space_dims_line}

Add the following products to the photo naturally:

{chr(10).join(item_descriptions)}{plants_section}

CRITICAL RULES:
- DO NOT change the camera angle, perspective, or viewpoint - keep EXACTLY the same view
- DO NOT regenerate or reimagine the space - ONLY add products to the existing photo
- DO NOT add, replace, expand, or redesign any floor surface: no floor tiles, pavers, patio slabs, deck boards, concrete, gravel, rugs, or hardscape unless that exact product is listed
- DO NOT replace grass with tiles or patio flooring. If there is grass in the original photo, it must remain grass
- DO NOT add new pergolas, roofs, beams, walls, fences, pathways, raised beds, or landscaping structures
- NEVER place rugs, carpets, or mats on grass, soil, or natural ground - they only belong on hard surfaces (deck, patio, concrete)
- Make products CLEARLY VISIBLE - they should be prominent in the scene
- Preserve EVERYTHING in the original photo - walls, floors, plants, furniture, architecture
- Match lighting direction and shadows
- Products should look physically present, not pasted
- No labels, watermarks, or text
- The output should look like the SAME photo with products added, not a new photo{plants_rule_text}

The space is a {request.scene_analysis.space_type}.
Style: {request.scene_analysis.style_observation}

Keep the EXACT same photo, just add the products."""


def _strip_data_url(image_base64: str) -> str:
    if "," in image_base64 and image_base64.startswith("data:"):
        return image_base64.split(",", 1)[1]
    return image_base64
