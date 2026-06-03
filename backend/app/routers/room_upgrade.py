"""
Room upgrade router.
Coordinates photo analysis, product search, budget optimization, and image generation.
Uses multi-image fusion to place actual product images into the scene.
"""
import asyncio
import base64
from typing import List, Optional

import httpx
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
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
)
from ..services.budget_optimizer_service import budget_optimizer_service
from ..services.gemini_service import gemini_service
from ..services.product_search_service import product_search_service
from ..services.scene_analysis_service import scene_analysis_service
from ..services.yard_advisor_service import yard_advisor_service
from ..services.scenario_context_service import YardInputs

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
  <style>
    :root { color-scheme: light dark; font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    body { margin: 0; background: #0f172a; color: #e5e7eb; }
    main { max-width: 1100px; margin: 0 auto; padding: 28px; }
    h1 { margin: 0 0 8px; font-size: 32px; }
    p { color: #94a3b8; }
    .card { background: #111827; border: 1px solid #334155; border-radius: 18px; padding: 18px; margin: 18px 0; }
    label { display: block; font-weight: 700; margin-bottom: 8px; }
    input, textarea, select, button { width: 100%; box-sizing: border-box; border-radius: 12px; border: 1px solid #475569; padding: 12px; font: inherit; }
    textarea, input, select { background: #020617; color: #e5e7eb; }
    textarea { min-height: 110px; resize: vertical; }
    button { margin-top: 14px; border: 0; background: #7c3aed; color: white; font-weight: 800; cursor: pointer; }
    button:disabled { opacity: 0.6; cursor: not-allowed; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; }
    .fields { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; }
    .field { display: flex; flex-direction: column; gap: 8px; }
    .checks { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 8px; }
    .checks label { display: inline-flex; align-items: center; gap: 6px; width: auto; font-weight: 500; color: #cbd5e1; }
    .checks input { width: auto; }
    img { width: 100%; border-radius: 14px; border: 1px solid #334155; object-fit: contain; background: #020617; }
    .product { display: grid; grid-template-columns: 96px 1fr; gap: 14px; align-items: start; }
    .product img { width: 96px; height: 96px; object-fit: cover; }
    .muted { color: #94a3b8; font-size: 14px; }
    .price { color: #a7f3d0; font-weight: 900; }
    .advice-block { margin: 12px 0; padding: 12px; border: 1px solid #334155; border-radius: 12px; background: #020617; }
    .advice-block h3 { margin: 0 0 8px; }
    a { color: #93c5fd; }
    pre { white-space: pre-wrap; overflow: auto; background: #020617; padding: 12px; border-radius: 12px; }
    .hidden { display: none; }
  </style>
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
            <label for="dimensions_sqm">Approx. size (m²)</label>
            <input id="dimensions_sqm" name="dimensions_sqm" type="number" min="0" step="1" placeholder="25" />
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
            <label for="environment_type">Environment</label>
            <select id="environment_type" name="environment_type">
              <option value="">Not sure</option>
              <option value="coastal">Coastal</option>
              <option value="suburban">Suburban</option>
              <option value="urban">Urban</option>
              <option value="rural">Rural</option>
              <option value="mountain">Mountain</option>
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

  <script>
    const form = document.getElementById('runnerForm');
    const statusEl = document.getElementById('status');
    const runButton = document.getElementById('runButton');
    const resultsEl = document.getElementById('results');

    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const imageFile = document.getElementById('image').files[0];
      const prompt = document.getElementById('prompt').value.trim();
      if (!imageFile) return;

      runButton.disabled = true;
      resultsEl.classList.add('hidden');
      document.getElementById('beforeImage').src = URL.createObjectURL(imageFile);

      try {
        statusEl.textContent = 'Analyzing photo, inferring budget, and finding products...';
        const formData = new FormData();
        formData.append('image', imageFile);
        formData.append('prompt', prompt);
        formData.append('currency', 'USD');
        appendOptionalField(formData, 'budget');
        appendOptionalField(formData, 'dimensions_sqm');
        appendOptionalField(formData, 'city_or_region');
        appendOptionalField(formData, 'orientation');
        appendOptionalField(formData, 'surface_type');
        appendOptionalField(formData, 'slope');
        appendOptionalField(formData, 'environment_type');
        appendOptionalField(formData, 'primary_purpose');
        appendOptionalField(formData, 'maintenance');
        appendOptionalField(formData, 'style_preference');
        appendOptionalField(formData, 'ownership');
        const whoUses = Array.from(document.querySelectorAll('input[name="who_uses"]:checked'))
          .map((input) => input.value);
        if (whoUses.length) formData.append('who_uses', whoUses.join(','));

        const analyzeResponse = await fetch('/api/v1/room-upgrade/analyze/upload', {
          method: 'POST',
          body: formData,
        });
        if (!analyzeResponse.ok) throw new Error(await analyzeResponse.text());
        const analyze = await analyzeResponse.json();

        statusEl.textContent = 'Generating after image with selected products...';
        const imageBase64 = await fileToBase64(imageFile);
        const generateResponse = await fetch('/api/v1/room-upgrade/generate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            image_base64: imageBase64,
            prompt,
            scene_analysis: analyze.scene_analysis,
            selected_products: analyze.selected_products,
          }),
        });
        if (!generateResponse.ok) throw new Error(await generateResponse.text());
        const generate = await generateResponse.json();

        renderResults(analyze, generate);
        statusEl.textContent = 'Done.';
      } catch (error) {
        console.error(error);
        statusEl.textContent = `Error: ${error.message || error}`;
      } finally {
        runButton.disabled = false;
      }
    });

    function renderResults(analyze, generate) {
      document.getElementById('afterImage').src = generate.after_image_url || '';
      document.getElementById('budgetSummary').textContent =
        `AI budget: $${Number(analyze.budget || 0).toFixed(2)} | Selected total: $${Number(analyze.total_estimated || 0).toFixed(2)}`;
      document.getElementById('generatedPrompt').textContent = generate.prompt_used || '';

      const productsEl = document.getElementById('products');
      productsEl.innerHTML = '';
      renderAdvice(analyze.design_advice);
      for (const selected of analyze.selected_products || []) {
        const product = selected.chosen_product;
        const attrs = [
          product.brand && `Brand: ${product.brand}`,
          product.material && `Material: ${product.material}`,
          product.color && `Color: ${product.color}`,
          product.dimensions && `Dimensions: ${product.dimensions}`,
          product.rating && `Rating: ${product.rating}`,
          product.review_count && `Reviews: ${product.review_count}`,
        ].filter(Boolean).join(' · ');
        const div = document.createElement('div');
        div.className = 'product card';
        div.innerHTML = `
          <img src="${escapeAttr(product.image_url || '')}" alt="" />
          <div>
            <h3>${escapeHtml(product.title || 'Product')}</h3>
            <p><span class="price">$${Number(product.price || 0).toFixed(2)}</span> at ${escapeHtml(product.store || '')}</p>
            <p class="muted">${escapeHtml(attrs || 'No extra attributes returned.')}</p>
            <p>${escapeHtml(product.detailed_description || product.description || '')}</p>
            <p><a href="${escapeAttr(product.buy_link || '#')}" target="_blank" rel="noreferrer">Open merchant link</a></p>
          </div>
        `;
        productsEl.appendChild(div);
      }
      resultsEl.classList.remove('hidden');
    }

    function renderAdvice(advice) {
      const adviceCard = document.getElementById('adviceCard');
      const adviceEl = document.getElementById('advice');
      adviceEl.innerHTML = '';

      if (!advice) {
        adviceCard.classList.add('hidden');
        return;
      }

      const blocks = [];
      if (advice.space_assessment?.summary) {
        blocks.push(`<div class="advice-block"><h3>Space assessment</h3><p>${escapeHtml(advice.space_assessment.summary)}</p></div>`);
      }
      if (advice.design_approach?.strategy) {
        blocks.push(`<div class="advice-block"><h3>Design approach</h3><p>${escapeHtml(advice.design_approach.strategy)}</p><p class="muted">${escapeHtml(advice.design_approach.reasoning || '')}</p></div>`);
      }
      if (advice.key_constraints?.length) {
        blocks.push(`<div class="advice-block"><h3>Key constraints</h3>${advice.key_constraints.map((item) => `<p><strong>${escapeHtml(item.title || '')}</strong><br />${escapeHtml(item.explanation || '')}<br /><span class="muted">${escapeHtml(item.user_action || '')}</span></p>`).join('')}</div>`);
      }
      if (advice.action_plan?.length) {
        blocks.push(`<div class="advice-block"><h3>Action plan</h3><ol>${advice.action_plan.map((item) => `<li><strong>${escapeHtml(item.action || '')}</strong><br />${escapeHtml(item.detail || '')}<br /><span class="muted">${escapeHtml(item.reasoning || '')}</span></li>`).join('')}</ol></div>`);
      }
      if (advice.warnings?.length) {
        blocks.push(`<div class="advice-block"><h3>Warnings</h3>${advice.warnings.map((item) => `<p><strong>${escapeHtml(item.title || '')}</strong>: ${escapeHtml(item.message || '')}</p>`).join('')}</div>`);
      }

      adviceEl.innerHTML = blocks.join('');
      adviceCard.classList.toggle('hidden', blocks.length === 0);
    }

    function appendOptionalField(formData, id) {
      const value = document.getElementById(id)?.value?.trim();
      if (value) formData.append(id, value);
    }

    function fileToBase64(file) {
      return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result).split(',')[1]);
        reader.onerror = reject;
        reader.readAsDataURL(file);
      });
    }

    function escapeHtml(value) {
      return String(value).replace(/[&<>"']/g, (char) => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'
      }[char]));
    }

    function escapeAttr(value) {
      return escapeHtml(value).replace(/`/g, '&#096;');
    }
  </script>
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
    dimensions_sqm: Optional[float] = Form(None),
    orientation: Optional[str] = Form(None),
    surface_type: Optional[str] = Form(None),
    slope: Optional[str] = Form(None),
    city_or_region: Optional[str] = Form(None),
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
    
    # Build yard inputs if any were provided
    yard_inputs = YardInputs(
        dimensions_sqm=dimensions_sqm,
        orientation=orientation,
        surface_type=surface_type,
        slope=slope,
        city_or_region=city_or_region,
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
        from ..services.scenario_context_service import scenario_context_service

        if scenario_context_service.has_inputs(yard_inputs):
            print("[Router] Yard inputs provided, generating design advice...")
            photo_analysis = (
                scene_analysis.model_dump()
                if hasattr(scene_analysis, "model_dump")
                else scene_analysis.dict()
            )
            advice_raw = await yard_advisor_service.generate_design_advice(
                yard_inputs,
                photo_analysis=photo_analysis,
            )
            design_advice = _parse_advice_to_model(advice_raw)

            if design_advice is not None:
                _apply_advice_to_shopping_list(scene_analysis, design_advice)

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

        return YardUpgradeAnalyzeResponse(
            design_advice=design_advice,
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


def build_room_upgrade_prompt_v2(
    request: RoomUpgradeGenerateRequest,
    num_product_images: int,
) -> str:
    """
    Build prompt that references product images by position.
    Image 1 = room photo, Images 2-N = product photos.
    """
    item_descriptions = []

    for index, selected in enumerate(request.selected_products, start=1):
        product = selected.chosen_product
        item = selected.shopping_list_item

        # Build detailed product description
        details = []
        if product.material:
            details.append(f"made of {product.material}")
        if product.color:
            details.append(f"in {product.color}")
        if product.dimensions:
            details.append(f"size: {product.dimensions}")

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

    # If we have product images, use multi-image prompt
    if num_product_images > 0:
        return f"""You are editing Image 1 (the room/outdoor space photo).{user_prompt}

I am providing {num_product_images} product reference images (Images 2-{num_product_images + 1}).
You MUST add these EXACT products to the scene - use their appearance from the reference images.

Products to add:

{chr(10).join(item_descriptions)}

CRITICAL RULES:
1. DO NOT change the camera angle, perspective, or viewpoint - keep EXACTLY the same view as the original photo
2. DO NOT regenerate or reimagine the space - ONLY add products to the existing photo
3. DO NOT add, replace, expand, or redesign any floor surface: no floor tiles, pavers, patio slabs, deck boards, concrete, gravel, rugs, or hardscape unless that exact product is listed
4. DO NOT replace grass with tiles or patio flooring. If there is grass in the original photo, it must remain grass
5. DO NOT add new pergolas, roofs, beams, walls, fences, pathways, raised beds, or landscaping structures
6. Use the EXACT visual appearance of each product from its reference image
7. Products must be CLEARLY VISIBLE in the final image - not subtle or hidden
8. Scale products appropriately for the existing visible surface; do not create a new support surface for them
9. Match lighting and shadows to the room
10. Place products naturally but prominently where specified
11. Preserve EVERYTHING in the original photo - walls, floors, grass, plants, furniture, architecture
12. NO labels, watermarks, text overlays, or price tags
13. The output should look like the SAME photo with products added, not a new photo

The space is a {request.scene_analysis.space_type}.
Current style: {request.scene_analysis.style_observation}

Generate the edited image now. Keep the EXACT same photo, just add the products."""

    # Fallback text-only prompt (when no product images available)
    return f"""You are editing the provided room or outdoor space photo.{user_prompt}

Add the following products to the photo naturally:

{chr(10).join(item_descriptions)}

CRITICAL RULES:
- DO NOT change the camera angle, perspective, or viewpoint - keep EXACTLY the same view
- DO NOT regenerate or reimagine the space - ONLY add products to the existing photo
- DO NOT add, replace, expand, or redesign any floor surface: no floor tiles, pavers, patio slabs, deck boards, concrete, gravel, rugs, or hardscape unless that exact product is listed
- DO NOT replace grass with tiles or patio flooring. If there is grass in the original photo, it must remain grass
- DO NOT add new pergolas, roofs, beams, walls, fences, pathways, raised beds, or landscaping structures
- Make products CLEARLY VISIBLE - they should be prominent in the scene
- Preserve EVERYTHING in the original photo - walls, floors, plants, furniture, architecture
- Match lighting direction and shadows
- Products should look physically present, not pasted
- No labels, watermarks, or text
- The output should look like the SAME photo with products added, not a new photo

The space is a {request.scene_analysis.space_type}.
Style: {request.scene_analysis.style_observation}

Keep the EXACT same photo, just add the products."""


def _strip_data_url(image_base64: str) -> str:
    if "," in image_base64 and image_base64.startswith("data:"):
        return image_base64.split(",", 1)[1]
    return image_base64
