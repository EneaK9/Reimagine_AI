# Cursor Prompt: Redesign Location Profile & Plant Specification Cards

Redesign the **Location Profile card** and **Plant Specification card** in this HTML file. Replace the current raw `<pre>` dump approach with proper structured UI components.

---

## Location Profile Card (`#locationCard`)

**Current state:** A `<pre>` tag dumping raw JSON.

**New design:**

Replace the `renderLocationProfile` function and the card's inner content with a structured layout that renders the profile as a visual dashboard. Use this structure:

```html
<div id="locationCard" class="card location-card">
  <h2>📍 Location Profile</h2>
  <div class="location-grid">
    <!-- Row 1: Identity -->
    <div class="location-section">
      <div class="location-hero">
        <span class="location-city" id="loc-city">—</span>
        <span class="location-country" id="loc-country">—</span>
      </div>
      <div class="location-tags" id="loc-tags"><!-- dynamic badges --></div>
    </div>

    <!-- Row 2: Climate stats -->
    <div class="location-stats" id="loc-stats"><!-- dynamic stat pills --></div>

    <!-- Row 3: Summaries -->
    <div class="location-summaries" id="loc-summaries"><!-- dynamic --></div>
  </div>
</div>
```

Update `renderLocationProfile(profile)` to populate these elements dynamically:

- **City/country hero**: large bold city name + country subtitle.
- **Tags**: render `city_context`, `usda_hardiness_zone`, `solar_lighting_viability`, `irrigation_required`, `data_quality` as small pill badges with subtle background colors (e.g. green for "high", amber for "recommended").
- **Climate stats**: a responsive grid of labeled stat tiles showing: `july_avg_high_c` (as "Peak Heat"), `annual_rainfall_mm` ("Annual Rain"), `annual_sunshine_hours` ("Sunshine hrs"), `uv_index_summer` ("UV Index"), `growing_season_days` ("Growing Days"), `avg_wind_kmh` ("Avg Wind").
- **Summaries**: render `plant_hardiness_summary` and `material_durability_summary` as two small labeled paragraphs with an icon prefix (🌿 and 🧱).
- If `profile` is null/undefined, hide the card as before.

**CSS to add:**

```css
.location-city { font-size: 1.6rem; font-weight: 700; }
.location-country { font-size: 0.9rem; color: var(--muted, #888); text-transform: uppercase; letter-spacing: 0.05em; }
.location-hero { display: flex; flex-direction: column; gap: 2px; }
.location-tags { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.location-tag { font-size: 0.75rem; padding: 2px 10px; border-radius: 999px; background: #f0f0f0; font-weight: 500; }
.location-stats { display: grid; grid-template-columns: repeat(auto-fill, minmax(110px, 1fr)); gap: 10px; margin-top: 16px; }
.stat-tile { background: #f7f7f7; border-radius: 8px; padding: 10px 12px; display: flex; flex-direction: column; gap: 4px; }
.stat-tile .stat-value { font-size: 1.2rem; font-weight: 700; }
.stat-tile .stat-label { font-size: 0.7rem; color: #888; text-transform: uppercase; letter-spacing: 0.04em; }
.location-summaries { margin-top: 16px; display: flex; flex-direction: column; gap: 8px; }
.location-summary { font-size: 0.85rem; line-height: 1.5; color: #444; }
```

---

## Plant Specification Card (`#plantSpecCard`)

**Current state:** A `<pre>` tag dumping the raw YAML/text string.

**New design:**

The plant spec comes in as a plain text string (YAML-like, `---` separated blocks). Parse and render each plant as a visual card.

Replace the `renderPlantSpec(spec)` function and the card's inner content:

```html
<div id="plantSpecCard" class="card plant-spec-card">
  <h2>🌿 Plant Specification</h2>
  <div id="plantSpec" class="plant-list"><!-- dynamic --></div>
</div>
```

Update `renderPlantSpec(spec)` to:

1. Split the string by `---` to get individual plant blocks.
2. For each block, extract fields by parsing lines like `Botanical name: ...`, `Common name: ...`, `Category: ...`, `Hardiness: ...`, and the freeform sections (`WHY THIS PLANT FOR THIS SITE:`, `WHY THIS PLANT FOR THIS BRIEF:`, `PROFESSIONAL CARE NOTE:`, `PAIRING SUGGESTION:`, `Seasonal role:`, `Availability:`).
3. Render each plant as a card like this:

```html
<div class="plant-card">
  <div class="plant-header">
    <div class="plant-name-group">
      <span class="plant-common-name">English Lavender</span>
      <span class="plant-botanical-name">Lavandula angustifolia 'Hidcote'</span>
    </div>
    <div class="plant-meta-badges">
      <span class="plant-badge category">Shrub</span>
      <span class="plant-badge hardiness">Zone 5</span>
    </div>
  </div>
  <div class="plant-sections">
    <div class="plant-section">
      <div class="plant-section-label">Why this site</div>
      <p>...</p>
    </div>
    <div class="plant-section">
      <div class="plant-section-label">Why this brief</div>
      <p>...</p>
    </div>
    <div class="plant-section">
      <div class="plant-section-label">Care note</div>
      <p>...</p>
    </div>
    <div class="plant-section">
      <div class="plant-section-label">Pairing</div>
      <p>...</p>
    </div>
    <div class="plant-footer">
      <span>🌸 <strong>Season:</strong> ...</span>
      <span>🛒 <strong>Availability:</strong> ...</span>
    </div>
  </div>
</div>
```

**CSS to add:**

```css
.plant-list { display: flex; flex-direction: column; gap: 20px; }
.plant-card { border: 1px solid #e5e5e5; border-radius: 10px; padding: 16px 20px; background: #fafafa; }
.plant-header { display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 10px; margin-bottom: 14px; }
.plant-name-group { display: flex; flex-direction: column; gap: 2px; }
.plant-common-name { font-size: 1.15rem; font-weight: 700; }
.plant-botanical-name { font-size: 0.8rem; font-style: italic; color: #777; }
.plant-meta-badges { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; }
.plant-badge { font-size: 0.72rem; padding: 3px 10px; border-radius: 999px; font-weight: 600; }
.plant-badge.category { background: #e8f5e9; color: #2e7d32; }
.plant-badge.hardiness { background: #e3f2fd; color: #1565c0; }
.plant-sections { display: flex; flex-direction: column; gap: 10px; }
.plant-section-label { font-size: 0.7rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; color: #999; margin-bottom: 3px; }
.plant-section p { font-size: 0.85rem; line-height: 1.6; color: #444; margin: 0; }
.plant-footer { display: flex; gap: 20px; flex-wrap: wrap; margin-top: 10px; padding-top: 10px; border-top: 1px solid #eee; font-size: 0.8rem; color: #555; }
```

---

## Constraints

- Keep all existing IDs (`locationCard`, `locationProfile`, `plantSpecCard`, `plantSpec`) so the rest of the JS still works.
- Do not change any other cards, forms, or logic.
- The `hidden` class toggling in `renderLocationProfile` and `renderPlantSpec` should remain intact.
- Keep `escapeHtml` usage where inserting untrusted text into the DOM.
