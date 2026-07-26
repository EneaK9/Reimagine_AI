# Editable 3D Room — Final Tool Selection & Implementation Plan

**Goal:** Replace the current photo → depth → static 2.5D relief mesh with a **structured 3D scene**: a room shell (walls / floor / ceiling) plus **one separate 3D object per furniture item**, so the user can select, move, rotate, swap, and recolor furniture and change wall/floor materials — now and in the future.

**Why the current pipeline can't get there:** `depth_service.py` (MiDaS → Open3D heightfield) produces one fused triangle soup. There are no objects, no occluded geometry, no metric scale, and no textures — editing is architecturally impossible on that representation. We keep it only as a fallback preview.

---

## 1. Final Tool Decisions

| Concern | Chosen tool | Why (vs. alternatives) |
|---|---|---|
| Scene representation | **Scene JSON (source of truth) + glTF/GLB assets, one named node per object** | Editing = mutating JSON, not regenerating meshes. GLB is what three.js and `<model-viewer>` load natively. USD/USDZ only as an import format from RoomPlan later. |
| Furniture detection (from photo) | **Gemini (already integrated) — object detection with bounding boxes + category + color/style description** | We already have the API key and `gemini_service.py`. Gemini returns labeled 2D boxes natively; no new infra. Self-hosted GroundingDINO+SAM2 is the later cost-optimization, not the MVP. |
| Depth / placement | **Depth Anything V2 (metric-indoor checkpoint)** replacing MiDaS DPT_Hybrid | Same self-hosted PyTorch pattern we already run, but *metric* depth → real-ish room dimensions and correct furniture placement/scale. Drop-in swap inside `depth_service.py`. |
| Room shell | **Procedural parametric room** (floor + 4 walls, dimensions estimated from metric depth + Gemini room analysis) | A clean box room with editable wall/floor materials beats a noisy reconstructed shell for a design app. This is what Planner 5D / IKEA Kreativ render too. |
| Furniture 3D assets — MVP | **Curated CC0 GLB catalog (~50–80 models)** retrieved by (category, size, style) | Instant, free, predictable quality, license-safe. Sources: Poly Haven, Sketchfab CC0, Kenney/Quaternius furniture packs. |
| Furniture 3D assets — V2 | **TRELLIS.2 (MIT license)** self-hosted or via fal.ai/Replicate; **Hunyuan3D 2.1** as alternative for best PBR textures | Open-source image-to-3D is production quality now. Generate a mesh from each furniture crop so it looks like *the user's* furniture. Hosted ≈ $0.05–0.30/asset; self-host needs ~24 GB GPU. |
| Premium capture — V2 | **Apple RoomPlan** (LiDAR iPhones/iPads Pro) | Free, on-device, parametric USDZ with real dimensions + furniture bounding boxes — slots directly into our scene JSON. iOS-Pro-only, so it's the premium path, not the default. |
| 3D editor on mobile | **three.js in a WebView** (`flutter_inappwebview`) with a JS⇄Dart bridge | We already render 3D via a webview (`model_viewer_plus` wraps `<model-viewer>`). three.js adds raycast selection, `TransformControls` drag/rotate, and material swaps in a few hundred lines. Unity embed = the path that already died in this repo; Flutter/Impeller 3D = too immature for an editor. |
| Natural-language edits | **Existing GPT-4 edit parser** (`rooms.py:157`, `_parse_edit_request`) wired to the new scene | Already built and tested — it outputs `{target, property, value}`; it just never had a structured scene to act on. Now it does. |
| Asset & scene storage | **PostgreSQL for scene JSON; object storage (S3-compatible) for GLB files** | Meshes on local disk (current) are lost on redeploy. Scene JSON in the existing Postgres keeps edits versionable (undo/redo, history). |
| NOT chosen | Planner 5D / Coohom white-label | Confirmed: their photo input yields a redesigned *image*, not editable 3D; editable 3D needs a floor plan. Enterprise pricing, zero differentiation. Re-evaluate only if we pivot to "fast to market over own tech". |
| Watch list | **PixARMesh (CVPR 2026)** — single photo → decomposed scene, per-object meshes | If code/weights release, it can replace steps detection+layout+retrieval with one model. Track the repo; do not block on it. |

---

## 2. Target Architecture

```
Photo ──► Backend pipeline ──► Scene JSON + assets ──► three.js editor (WebView)
                                                            │
User edits (drag / recolor / swap / chat command) ──────────┘
        └──► scene JSON PATCH ──► persisted in Postgres (versioned)
```

**Scene JSON (source of truth), stored per conversation/user:**

```json
{
  "scene_id": "uuid",
  "version": 3,
  "room": {
    "width_m": 4.2, "depth_m": 3.6, "height_m": 2.6,
    "wall_material": {"color": "#F5F0E8", "texture": null},
    "floor_material": {"color": "#B08968", "texture": "oak_01"}
  },
  "objects": [
    {
      "id": "sofa_1",
      "category": "sofa",
      "asset": {"type": "catalog", "ref": "sofa_modern_02.glb"},
      "transform": {"pos": [1.2, 0, 0.8], "rot_y_deg": 90, "scale": [1,1,1]},
      "material_override": {"color": "#3B5D8F"},
      "source": {"detected_from": "photo", "bbox": [120, 340, 610, 720], "confidence": 0.93}
    }
  ]
}
```

**glTF assembly rule:** every object = one named node (`sofa_1`, `wall_north`, `floor`). The editor addresses nodes by name; the NL-edit parser's `target` maps to node names.

---

## 3. Step-by-Step Plan

### Phase 0 — Foundations (≈ 2–3 days)

1. **Create the scene model.**
   - `backend/app/models/scene.py`: Pydantic models `Scene`, `RoomShell`, `SceneObject`, `Transform`, `MaterialOverride` (mirror the JSON above).
   - New Postgres table `scenes` (`id`, `user_id`, `conversation_id`, `version`, `data JSONB`, `created_at`, `updated_at`) + `scene_versions` for undo history. Migration alongside the existing user/conversation tables.
2. **Scene service + router.**
   - `backend/app/services/scene_service.py`: create / get / patch (JSON-merge with version bump) / list versions / revert.
   - `backend/app/routers/scenes.py` under `/api/v1/scenes`: `POST /generate` (photo → scene, async), `GET /{id}`, `PATCH /{id}` (edit ops), `GET /{id}/versions`, `POST /{id}/revert/{version}`.
3. **Asset catalog skeleton.**
   - `backend/data/catalog/` with `catalog.json` (per asset: id, category, style tags, real-world dims in meters, default material slots, license note, file).
   - Seed with 10 placeholder GLBs to unblock frontend work; grow to ~50–80 in Phase 2.
   - `GET /api/v1/assets/{id}` serves GLBs with cache headers (move to S3-compatible storage before production deploy).

### Phase 1 — Photo → Structured Scene pipeline (≈ 1–1.5 weeks)

4. **Furniture detection** — `backend/app/services/scene_builder.py`.
   - One Gemini call on the photo, prompt returns strict JSON: room type, estimated room dims, and per item `{category, bbox_2d, dominant_color, style_keywords}`. Validate with Pydantic; retry once on malformed JSON.
5. **Metric depth** — upgrade `depth_service.py`.
   - Swap MiDaS DPT_Hybrid → **Depth Anything V2 metric (indoor)**. Keep the old GLB path behind a flag as fallback preview.
6. **Placement solver** — in `scene_builder.py`.
   - For each detected item: sample metric depth inside its bbox → back-project bbox center to camera space → assume floor plane (y=0), estimate footprint from bbox extent × depth → produce `pos`, `rot_y` (default facing camera), `scale` clamped to the catalog asset's real dims. Overlap-resolve by nudging along x/z.
7. **Room shell estimation.**
   - Room width/depth/height from metric depth extremes + Gemini's estimate (average them, clamp to sane bounds 2–8 m). Wall/floor colors sampled from photo regions Gemini labels as wall/floor. Build the parametric shell (5 quads + baked openings later).
8. **Asset retrieval.**
   - Match (category, footprint size, style tags) against `catalog.json`; nearest-size wins; store `material_override.color` from the detected dominant color.
9. **Assemble & persist.**
   - Emit scene JSON v1 → store in Postgres. Optional: server-side merged-GLB export endpoint (`trimesh`) for share/download — the editor itself loads shell + assets individually.
10. **Wire into chat flow.**
    - Replace the mesh auto-regen in `chat.py:159-170`: when a conversation has a `scene_id` and the user requests an edit, route to the edit parser (Phase 3) instead of regenerating everything.

### Phase 2 — three.js editor in Flutter (≈ 1–1.5 weeks, parallel with Phase 1 after step 3)

11. **Editor web app** — `mobile/assets/editor/` (built HTML/JS bundle, three.js via npm + esbuild; keep it a tiny standalone project in `editor/` at repo root).
    - Loads scene JSON from the bridge; builds the shell procedurally; loads each object's GLB via `GLTFLoader` (with `DRACOLoader`); applies transforms + material overrides.
    - **Select:** raycast on tap → highlight (emissive outline) → show object toolbar.
    - **Move/rotate:** drag on floor plane (XZ-constrained), rotate handle for `rot_y`; grid-snap toggle.
    - **Recolor/material:** color picker + material presets applied to the node's materials.
    - **Swap:** category-filtered catalog sheet → replace asset ref, keep transform.
    - **Walls/floor:** tap wall/floor → same material panel.
    - Every edit emits a JSON-patch op over the bridge; debounce-save.
12. **Flutter host screen** — `mobile/lib/screens/scene_editor_screen.dart`.
    - `flutter_inappwebview` hosting the bundle; Dart⇄JS bridge (`loadScene`, `applyOp`, `onSceneChanged`, `selectObject`); undo/redo buttons calling version endpoints; replace the scan screen's "view mesh" result with "open editor" once a scene exists. Keep `model_viewer_plus` only for the legacy fallback preview.
13. **API client** — extend `api_service.dart` + a new `SceneProvider` (mirror `chat_provider.dart` patterns): generate/get/patch/revert scene.

### Phase 3 — AI edits & polish (≈ 1 week)

14. **Natural-language editing.**
    - Port `_parse_edit_request` from `rooms.py` into `scene_service.py`; extend the schema to `{target: object_id|category|wall|floor, action: move|rotate|recolor|swap|remove|add, value}`. Ground `target` against the actual scene JSON (send the object list in the prompt). Apply as a normal PATCH → editor updates live via the bridge.
    - Chat integration: "make the sofa navy and move it under the window" works from the chat screen when a scene exists.
15. **Add-object flow.** "Add a floor lamp" → catalog match → place at a free floor spot; manual placement afterwards in the editor.
16. **Cleanup.**
    - Delete/param-gate the dead code paths: Unity screens (`room_editor_screen.dart`), `unity_ar_scanner/` (archive branch), old mesh regen loop. Keep `/depth` endpoints only if the fallback preview stays.
    - Move mesh/asset storage off local disk to S3-compatible storage; add size limits and GLB validation on any upload path.

### Phase 4 — V2 (later, in priority order)

17. **Per-object generation:** TRELLIS.2 (start hosted via fal.ai/Replicate; self-host on a 24 GB GPU if volume justifies). Pipeline: SAM-cut the furniture crop → image-to-3D → auto-scale to detected footprint → cache per user. Fall back to catalog on failure/timeouts.
18. **RoomPlan capture path (iOS Pro):** native Swift module → USDZ → server-side USD→scene-JSON converter (walls/doors/windows/furniture boxes map 1:1 to our schema). Gate by LiDAR capability detection.
19. **Multi-photo / panorama support** for better shells (HorizonNet-style) — only if single-photo shells prove too inaccurate.
20. **PixARMesh adoption** if code/weights release — would replace steps 4–8 with one model; the scene JSON contract means the editor doesn't change at all.

---

## 4. Costs & Licensing Summary

| Item | Cost | License |
|---|---|---|
| Gemini detection call | ~fractions of a cent/photo (existing key) | API ToS |
| Depth Anything V2 | self-hosted, CPU-viable / small GPU | Apache-2.0 (metric ckpts: check variant) |
| Catalog assets | free | CC0 only — record license per asset in catalog.json |
| three.js, GLTFLoader | free | MIT |
| TRELLIS.2 (V2) | ~$0.05–0.30/asset hosted, or 24 GB GPU self-host | MIT |
| Hunyuan3D 2.1 (V2 alt) | similar | Tencent community license — review before commercial use |
| RoomPlan (V2) | free, on-device | Apple SDK; LiDAR devices only |

## 5. Risks & Mitigations

- **Placement accuracy from one photo is approximate.** Mitigation: it only needs to be a *good starting layout* — the editor exists precisely so users adjust. Ship grid-snap and easy drag.
- **Catalog assets won't match the user's furniture.** Expected for MVP; V2 generation (step 17) is the fix. Meanwhile, color-matching the override narrows the gap.
- **WebView bridge complexity.** Keep the protocol tiny (5 messages) and version it; the editor bundle is testable standalone in a desktop browser.
- **Backend model cold-starts** (already a problem with MiDaS). Load depth model at startup, not lazily; document GPU/CPU expectations in README.

## 6. Definition of Done (MVP = end of Phase 3)

From one room photo, the app produces a 3D room with the shell and each detected furniture piece as a separate object; the user can tap-select, drag, rotate, recolor, swap, and delete objects, change wall/floor colors, undo/redo, and issue the same edits in plain language through chat — with the scene persisted and re-openable across sessions.
