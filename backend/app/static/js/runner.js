console.log('SCRIPT START');
const form = document.getElementById('runnerForm');
const statusEl = document.getElementById('status');
const runButton = document.getElementById('runButton');
const resultsEl = document.getElementById('results');
console.log('DOM elements:', {form: !!form, statusEl: !!statusEl, runButton: !!runButton, resultsEl: !!resultsEl});

(function populateFromUrl() {
  const params = new URLSearchParams(window.location.search);
  const textFields = ['prompt', 'budget', 'yard_length', 'yard_width', 'city_or_region', 'orientation', 'surface_type', 'slope', 'setting', 'primary_purpose', 'maintenance', 'style_preference', 'ownership', 'unit_system'];
  for (const field of textFields) {
    const value = params.get(field);
    const el = document.getElementById(field);
    if (value && el) {
      el.value = value;
    }
  }
  const whoUses = params.get('who_uses');
  if (whoUses) {
    for (const val of whoUses.split(',')) {
      const cb = document.querySelector(`input[name="who_uses"][value="${val}"]`);
      if (cb) cb.checked = true;
    }
  }
  const advancedFields = ['budget', 'yard_length', 'yard_width', 'city_or_region', 'orientation', 'surface_type', 'slope', 'setting', 'primary_purpose', 'maintenance', 'style_preference', 'ownership'];
  if (advancedFields.some(f => params.get(f))) {
    document.querySelector('details')?.setAttribute('open', '');
  }
})();

console.log('About to add event listener');
form.addEventListener('submit', async (event) => {
  console.log('SUBMIT HANDLER CALLED');
  event.preventDefault();
  console.log('preventDefault called');
  const imageFile = document.getElementById('image').files[0];
  const prompt = document.getElementById('prompt').value.trim();
  if (!imageFile) {
    statusEl.textContent = 'Error: Please select an image file first.';
    return;
  }

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
    appendOptionalField(formData, 'unit_system');
    appendOptionalField(formData, 'yard_length');
    appendOptionalField(formData, 'yard_width');
    appendOptionalField(formData, 'city_or_region');
    appendOptionalField(formData, 'orientation');
    appendOptionalField(formData, 'surface_type');
    appendOptionalField(formData, 'slope');
    appendSettingMapping(formData);
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
        unit_system: document.getElementById('unit_system')?.value || null,
        yard_length: parseFloat(document.getElementById('yard_length')?.value || '') || null,
        yard_width: parseFloat(document.getElementById('yard_width')?.value || '') || null,
        plant_spec: analyze.plant_spec || null,
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
  renderLocationProfile(analyze.location_profile);
  renderPlantSpec(analyze.plant_spec);
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

function renderLocationProfile(profile) {
  const card = document.getElementById('locationCard');
  if (!profile) {
    card.classList.add('hidden');
    document.getElementById('loc-city').textContent = '—';
    document.getElementById('loc-country').textContent = '—';
    document.getElementById('loc-tags').innerHTML = '';
    document.getElementById('loc-stats').innerHTML = '';
    document.getElementById('loc-summaries').innerHTML = '';
    return;
  }

  document.getElementById('loc-city').textContent = profile.city || '—';
  document.getElementById('loc-country').textContent = profile.country_or_region || '';

  const tagsEl = document.getElementById('loc-tags');
  tagsEl.innerHTML = '';
  const tagDefs = [
    ['context', profile.city_context],
    ['zone', profile.usda_hardiness_zone],
    ['solar', profile.solar_lighting_viability],
    ['irrigation', profile.irrigation_required],
    ['data', profile.data_quality],
  ].filter((pair) => pair[1] !== null && pair[1] !== undefined && String(pair[1]).trim() !== '');

  const tagClass = (label, value) => {
    const v = String(value).toLowerCase();
    if (label === 'data') {
      if (v === 'high') return 'good';
      if (v === 'medium') return 'warn';
      if (v === 'low') return 'bad';
    }
    if (label === 'irrigation' && v === 'mandatory') return 'warn';
    if (label === 'solar' && v === 'not_recommended') return 'warn';
    return '';
  };

  for (const [label, value] of tagDefs) {
    const span = document.createElement('span');
    span.className = `location-tag ${tagClass(label, value)}`.trim();
    span.textContent = `${label}: ${String(value).replaceAll('_', ' ')}`;
    tagsEl.appendChild(span);
  }

  const statsEl = document.getElementById('loc-stats');
  statsEl.innerHTML = '';
  const stats = [
    ['Peak Heat', profile.july_avg_high_c != null ? `${Number(profile.july_avg_high_c).toFixed(0)}°C` : null],
    ['Annual Rain', profile.annual_rainfall_mm != null ? `${Number(profile.annual_rainfall_mm).toFixed(0)} mm` : null],
    ['Sunshine hrs', profile.annual_sunshine_hours != null ? `${Number(profile.annual_sunshine_hours).toFixed(0)}` : null],
    ['UV Index', profile.uv_index_summer != null ? String(profile.uv_index_summer) : null],
    ['Growing Days', profile.growing_season_days != null ? String(profile.growing_season_days) : null],
    ['Avg Wind', profile.avg_wind_kmh != null ? `${Number(profile.avg_wind_kmh).toFixed(0)} km/h` : null],
  ].filter((x) => x[1]);

  for (const [label, value] of stats) {
    const tile = document.createElement('div');
    tile.className = 'stat-tile';
    tile.innerHTML = `<div class="stat-value">${escapeHtml(value)}</div><div class="stat-label">${escapeHtml(label)}</div>`;
    statsEl.appendChild(tile);
  }

  const summariesEl = document.getElementById('loc-summaries');
  summariesEl.innerHTML = '';
  const summaries = [
    ['🌿', 'Plants', profile.plant_hardiness_summary],
    ['🧱', 'Materials', profile.material_durability_summary],
  ].filter((s) => s[2]);

  for (const [icon, title, text] of summaries) {
    const div = document.createElement('div');
    div.className = 'location-summary';
    div.innerHTML = `${escapeHtml(icon)} <strong>${escapeHtml(title)}:</strong> ${escapeHtml(String(text))}`;
    summariesEl.appendChild(div);
  }

  card.classList.remove('hidden');
}

function renderPlantSpec(spec) {
  const card = document.getElementById('plantSpecCard');
  const el = document.getElementById('plantSpec');
  if (!spec) {
    card.classList.add('hidden');
    el.innerHTML = '';
    return;
  }
  const text = String(spec || '').trim();
  if (!text) {
    card.classList.add('hidden');
    el.innerHTML = '';
    return;
  }

  const blocks = text
    .split(/\n\s*---\s*\n/g)
    .map((b) => b.trim())
    .filter(Boolean);

  const plants = [];
  const extras = [];

  for (const block of blocks) {
    const hasPlantShape = /Botanical name:/i.test(block) || /^PLANT\s+\d+/im.test(block);
    if (!hasPlantShape) {
      extras.push(block);
      continue;
    }

    const lineValue = (label) => {
      const safe = String(label).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      const m = block.match(new RegExp(`${safe}\\s*:\\s*(.+)$`, 'im'));
      return m ? m[1].trim() : '';
    };

    const sectionValue = (label) => {
      const safe = String(label).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      const start = block.search(new RegExp(`^${safe}\\s*:$`, 'im'));
      if (start === -1) return '';
      const after = block.slice(start).split(/\r?\n/);
      after.shift();
      const lines = [];
      for (const ln of after) {
        if (/^[A-Z][A-Z _()/-]{3,}:\s*$/m.test(ln.trim())) break;
        lines.push(ln);
      }
      return lines.join('\n').trim();
    };

    const botanical = lineValue('Botanical name');
    const common = lineValue('Common name');
    const category = lineValue('Category');
    const hardiness = lineValue('Hardiness');

    const whySite = sectionValue('WHY THIS PLANT FOR THIS SITE');
    const whyBrief = sectionValue('WHY THIS PLANT FOR THIS BRIEF');
    const care = sectionValue('PROFESSIONAL CARE NOTE');
    const pairing = sectionValue('PAIRING SUGGESTION');

    const seasonal = lineValue('Seasonal role');
    const availability = lineValue('Availability');

    const key = (botanical || common || '').toLowerCase().replaceAll(/[^a-z0-9]+/g, '-').replaceAll(/^-+|-+$/g, '');
    plants.push({
      key: key || `plant-${plants.length + 1}`,
      botanical,
      common,
      category,
      hardiness,
      whySite,
      whyBrief,
      care,
      pairing,
      seasonal,
      availability,
    });
  }

  el.innerHTML = '';
  for (const plant of plants) {
    const div = document.createElement('div');
    div.className = 'plant-card';
    div.innerHTML = `
      <div class="plant-header">
        <div class="plant-name-group">
          <span class="plant-common-name">${escapeHtml(plant.common || plant.botanical || 'Plant')}</span>
          <span class="plant-botanical-name">${escapeHtml(plant.botanical || '')}</span>
        </div>
        <div class="plant-meta-badges">
          ${plant.category ? `<span class="plant-badge category">${escapeHtml(plant.category)}</span>` : ''}
          ${plant.hardiness ? `<span class="plant-badge hardiness">${escapeHtml(plant.hardiness)}</span>` : ''}
        </div>
      </div>
      <div class="plant-body">
        <div class="plant-image">
          <div class="image-placeholder" data-plant-img="${escapeAttr(plant.key)}">Loading image…</div>
        </div>
        <div class="plant-sections">
          ${plant.whySite ? `<div class="plant-section"><div class="plant-section-label">Why this site</div><p>${escapeHtml(plant.whySite)}</p></div>` : ''}
          ${plant.whyBrief ? `<div class="plant-section"><div class="plant-section-label">Why this brief</div><p>${escapeHtml(plant.whyBrief)}</p></div>` : ''}
          ${plant.care ? `<div class="plant-section"><div class="plant-section-label">Care note</div><p>${escapeHtml(plant.care)}</p></div>` : ''}
          ${plant.pairing ? `<div class="plant-section"><div class="plant-section-label">Pairing</div><p>${escapeHtml(plant.pairing)}</p></div>` : ''}
          ${(plant.seasonal || plant.availability) ? `
            <div class="plant-footer">
              ${plant.seasonal ? `<span>🌸 <strong>Season:</strong> ${escapeHtml(plant.seasonal)}</span>` : ''}
              ${plant.availability ? `<span>🛒 <strong>Availability:</strong> ${escapeHtml(plant.availability)}</span>` : ''}
            </div>` : ''}
        </div>
      </div>
    `;
    el.appendChild(div);
  }

  (async () => {
    try {
      const resp = await fetch('/api/v1/room-upgrade/plant-images', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          plants: plants.map((p) => ({
            key: p.key,
            botanical_name: p.botanical,
            common_name: p.common,
          })),
        }),
      });
      if (!resp.ok) {
        console.error('Plant images fetch failed:', resp.status);
        for (const p of plants) {
          const holder = document.querySelector(`[data-plant-img="${CSS.escape(p.key)}"]`);
          if (holder) holder.textContent = 'Image unavailable';
        }
        return;
      }
      const data = await resp.json();
      const images = data?.images || {};
      for (const p of plants) {
        const url = images[p.key];
        const holder = document.querySelector(`[data-plant-img="${CSS.escape(p.key)}"]`);
        if (!holder) continue;
        if (!url) {
          holder.textContent = 'No image found';
          continue;
        }
        const img = document.createElement('img');
        img.src = String(url);
        img.alt = p.common || p.botanical || 'Plant photo';
        holder.replaceWith(img);
      }
    } catch (e) {
      console.error('Plant images error:', e);
      for (const p of plants) {
        const holder = document.querySelector(`[data-plant-img="${CSS.escape(p.key)}"]`);
        if (holder) holder.textContent = 'Image unavailable';
      }
    }
  })();

  card.classList.remove('hidden');
}

function appendSettingMapping(formData) {
  const setting = document.getElementById('setting')?.value?.trim();
  if (!setting) return;

  if (setting === 'coastal_exposed') {
    formData.append('environment_type', 'coastal');
    formData.append('city_context', 'coastal');
    return;
  }

  if (setting === 'mountain') {
    formData.append('environment_type', 'mountain');
    formData.append('city_context', 'inland');
    return;
  }

  if (['urban', 'suburban', 'rural'].includes(setting)) {
    formData.append('environment_type', setting);
  }
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
