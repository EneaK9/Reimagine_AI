# Room Upgrade App — Full Implementation Plan

> **Read this entire file before writing a single line of code.**
> This document describes the complete architecture, data flow, and implementation steps for building a room/yard upgrade app. The user uploads a photo, states a budget, and receives: (1) a curated product list with real buy links, (2) an AI-generated "after" photo showing those products placed in their space.

---

## What Already Exists (Do Not Rebuild)

| Module | What it does | How to call it |
|---|---|---|
| **Stage 1 — Photo upload UI** | User uploads a photo and types a prompt | Already exists — reuse as-is |
| **Stage 3 — Product search** | Takes a text description (e.g. "tall lamp 20cm diameter around $50") and returns up to 10 real products with title, price, image URL, buy link, reviews from Amazon/eBay/IKEA/Target | Already exists — call it with a description string, get back an array of product objects |
| **Nano Banana wrapper** | Takes a photo + text prompt + Google Gemini API key, returns an edited photo | Already exists — call it with `(imageFile, promptString)`, get back an image |

**Your job is to build the glue between these three modules and the UI that presents the result.**

---

## High-Level User Flow

```
User uploads photo + types "make my backyard look better for $100"
        ↓
[STEP A] Claude Vision analyzes the photo → produces a structured shopping list JSON
        ↓
[STEP B] For each item in the list, call Stage 3 (product search) → get real products
        ↓
[STEP C] Claude (text only) picks the best combination of products that fits under $100
        ↓
[STEP D] Show the user the product list UI (approve/edit step — optional but recommended)
        ↓
[STEP E] Build a rich Nano Banana prompt using product names, colors, descriptions + pass
         the room photo AND each product image URL as reference images
        ↓
[STEP F] Call Nano Banana → get back the edited "after" photo
        ↓
[STEP G] Show the before/after photo side by side + shopping cards for each product
```

---

## Data Models

Define these TypeScript interfaces (or plain JS objects if not using TypeScript) at the start of your implementation.

### UserInput
```ts
interface UserInput {
  photo: File;               // The uploaded room/yard photo
  prompt: string;            // e.g. "make my backyard look better for $100"
  budget: number;            // Parsed from the prompt, e.g. 100
  currency: string;          // Default "USD"
}
```

### ShoppingListItem
```ts
interface ShoppingListItem {
  itemName: string;          // e.g. "outdoor string lights"
  searchDescription: string; // e.g. "outdoor patio string lights 30ft warm white"
  budgetAllocation: number;  // How much of the total budget to spend on this item
  placement: string;         // e.g. "strung above the seating area in a zigzag"
  priority: "must-have" | "nice-to-have";
}
```

### Product (returned by Stage 3)
```ts
interface Product {
  title: string;
  price: number;
  currency: string;
  imageUrl: string;
  buyLink: string;
  store: string;             // "amazon" | "ikea" | "target" | "ebay"
  rating?: number;
  reviewCount?: number;
  description?: string;
}
```

### SelectedProduct (after budget optimization step)
```ts
interface SelectedProduct {
  shoppingListItem: ShoppingListItem;
  chosenProduct: Product;    // The one product chosen for this item
  allCandidates: Product[];  // All 10 returned by Stage 3 (store for fallback)
}
```

### AppState
```ts
interface AppState {
  status: "idle" | "analyzing" | "searching" | "optimizing" | "generating" | "done" | "error";
  userInput: UserInput | null;
  shoppingList: ShoppingListItem[];
  selectedProducts: SelectedProduct[];
  afterPhotoUrl: string | null;
  errorMessage: string | null;
}
```

---

## Step A — Scene Analysis with Claude Vision

### What this step does
Send the user's uploaded photo + their text prompt to the Claude API (claude-sonnet-4-6 or better). Ask it to analyze the space and produce a structured shopping list as JSON.

### API call
Use the Anthropic API. Send the image as base64. System prompt + user message pattern.

```js
// Convert the uploaded File to base64
async function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result.split(",")[1]);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

async function analyzeScene(userInput) {
  const base64Image = await fileToBase64(userInput.photo);
  const mediaType = userInput.photo.type; // e.g. "image/jpeg"

  const response = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      model: "claude-sonnet-4-6",
      max_tokens: 1000,
      system: `You are an interior and exterior design assistant. 
You analyze photos of rooms, yards, patios, and living spaces. 
You return ONLY valid JSON — no markdown, no explanation, no backticks.
The JSON must exactly match the schema provided.`,
      messages: [
        {
          role: "user",
          content: [
            {
              type: "image",
              source: {
                type: "base64",
                media_type: mediaType,
                data: base64Image,
              },
            },
            {
              type: "text",
              text: `The user says: "${userInput.prompt}"
Their budget is $${userInput.budget}.

Analyze this photo and return a JSON object with this exact structure:
{
  "spaceType": "string — e.g. 'small backyard patio', 'living room', 'bedroom'",
  "existingItems": ["array of strings describing what's already there"],
  "styleObservation": "one sentence about the current style/vibe",
  "shoppingList": [
    {
      "itemName": "short product category name",
      "searchDescription": "detailed search query for finding this product, include size, color, material, and target price",
      "budgetAllocation": number (dollars, must sum to at most ${userInput.budget}),
      "placement": "specific placement instruction, e.g. 'hung in a zigzag pattern above the seating area'",
      "priority": "must-have or nice-to-have"
    }
  ]
}

Rules:
- The budgetAllocation values across all items must sum to AT MOST $${userInput.budget}.
- Include 2 to 4 items maximum.
- The searchDescription should be detailed enough to find a real product — include color, size, style, and approximate price.
- The placement should be specific enough to guide image generation later.
- Return ONLY the JSON object. No backticks, no explanation.`,
            },
          ],
        },
      ],
    }),
  });

  const data = await response.json();
  const text = data.content[0].text;

  // Strip any accidental markdown fences
  const cleaned = text.replace(/```json|```/g, "").trim();
  return JSON.parse(cleaned);
}
```

### What you get back (example)
```json
{
  "spaceType": "small backyard patio",
  "existingItems": ["two plastic chairs", "small wooden table", "concrete floor"],
  "styleObservation": "Bare and functional with no decorative elements.",
  "shoppingList": [
    {
      "itemName": "outdoor string lights",
      "searchDescription": "outdoor patio Edison bulb string lights 25ft warm white waterproof",
      "budgetAllocation": 40,
      "placement": "strung in a zigzag pattern above the seating area",
      "priority": "must-have"
    },
    {
      "itemName": "outdoor rug",
      "searchDescription": "outdoor rug 4x6 grey woven polypropylene weather resistant",
      "budgetAllocation": 45,
      "placement": "placed flat on the concrete floor beneath the chairs and table",
      "priority": "must-have"
    },
    {
      "itemName": "potted plant",
      "searchDescription": "outdoor potted succulent or small shrub in terracotta pot",
      "budgetAllocation": 15,
      "placement": "placed in the corner of the patio near the fence",
      "priority": "nice-to-have"
    }
  ]
}
```

---

## Step B — Product Search for Each Item

### What this step does
For each item in the `shoppingList` array returned by Step A, call the existing Stage 3 product search module. Run all searches in parallel (Promise.all) to keep it fast.

```js
async function searchAllProducts(shoppingList) {
  // Run all product searches in parallel
  const searchPromises = shoppingList.map(async (item) => {
    // Stage 3 already exists — call it with the searchDescription
    const products = await searchProducts(item.searchDescription);
    // searchProducts() is your existing Stage 3 function
    // It returns an array of up to 10 Product objects
    return {
      shoppingListItem: item,
      allCandidates: products,
    };
  });

  return Promise.all(searchPromises);
}
```

### Error handling for this step
If a search returns 0 results, do NOT fail the whole flow. Instead:
- Log the failed item
- Try a simplified version of the searchDescription (strip size/color, keep only category + budget)
- If still 0 results, remove that item from the list and continue

```js
async function searchWithFallback(item) {
  let products = await searchProducts(item.searchDescription);
  
  if (products.length === 0) {
    // Fallback: simpler query
    const simpleQuery = `${item.itemName} under $${item.budgetAllocation}`;
    products = await searchProducts(simpleQuery);
  }

  return {
    shoppingListItem: item,
    allCandidates: products,
  };
}
```

---

## Step C — Budget Optimization (Pick the Best Combo)

### What this step does
After Step B you have, for each shopping list item, a list of real products with real prices. Some products may be over budget for their slot, or the combination may exceed $100 total. You need to pick one product per item such that the total is under the user's budget.

Do this with a second Claude API call (text only, no image). Pass in all the candidates and ask Claude to pick the best combination.

```js
async function optimizeBudget(searchResults, totalBudget) {
  // Build a summary of all candidates for Claude to reason over
  const summaryLines = searchResults.map((result, i) => {
    const candidates = result.allCandidates.slice(0, 5).map((p, j) => 
      `    Option ${j+1}: "${p.title}" — $${p.price} at ${p.store} — Rating: ${p.rating ?? "N/A"}`
    ).join("\n");
    
    return `Item ${i+1}: ${result.shoppingListItem.itemName} (target: $${result.shoppingListItem.budgetAllocation})\n${candidates}`;
  }).join("\n\n");

  const response = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      model: "claude-sonnet-4-6",
      max_tokens: 1000,
      system: `You are a budget shopping assistant. You receive a list of items with candidate products and a total budget. You pick the best combination. Return ONLY valid JSON, no markdown, no explanation.`,
      messages: [{
        role: "user",
        content: `Total budget: $${totalBudget}

${summaryLines}

Pick one option per item such that the total price is under $${totalBudget}.
Prefer: best rating, closest to budget allocation, most reputable store.
If no combination fits under budget, pick the cheapest option for each item even if slightly over.

Return this exact JSON structure:
{
  "selections": [
    {
      "itemIndex": 0,
      "optionIndex": 0,
      "reasoning": "one short sentence"
    }
  ],
  "totalEstimated": 85.97,
  "withinBudget": true
}

itemIndex is 0-based index of the item. optionIndex is 0-based index of the chosen option.
Return ONLY the JSON.`
      }]
    })
  });

  const data = await response.json();
  const text = data.content[0].text.replace(/```json|```/g, "").trim();
  const parsed = JSON.parse(text);

  // Map the selections back to actual product objects
  return parsed.selections.map((sel) => ({
    shoppingListItem: searchResults[sel.itemIndex].shoppingListItem,
    chosenProduct: searchResults[sel.itemIndex].allCandidates[sel.optionIndex],
    allCandidates: searchResults[sel.itemIndex].allCandidates,
  }));
}
```

---

## Step D — Product Approval UI (Show Before Generating)

### What this step does
Before calling Nano Banana (which costs money and takes time), show the user what products were selected. This is a critical UX moment — the user can see the product list, swap out individual products, and then confirm before the image is generated.

### What to render
For each `SelectedProduct`, render a card with:
- Product thumbnail image (from `chosenProduct.imageUrl`)
- Product title
- Price
- Store name + buy link (make it tappable — opens in new tab)
- Star rating if available
- A "swap" button that shows the other `allCandidates` as alternatives

Below the cards, show:
- Total estimated cost
- A prominent **"Generate my upgrade →"** button

### State during this step
Set `appState.status = "optimizing"` while Steps A–C run.
Set `appState.status = "done"` temporarily (or a new status like `"awaiting_approval"`) once the product list is ready, to show the approval UI.
Only proceed to Step E when the user clicks "Generate."

---

## Step E — Build the Nano Banana Prompt

### What this step does
Construct the text prompt that tells Nano Banana exactly what to add to the photo, where to place it, and how it should look. This prompt is built programmatically from the `SelectedProduct` array. Prompt quality directly determines image quality.

```js
function buildNanaBananaPrompt(selectedProducts, sceneAnalysis) {
  const itemDescriptions = selectedProducts.map((sel, i) => {
    const p = sel.chosenProduct;
    const item = sel.shoppingListItem;
    return `${i + 1}. ${p.title} (${item.itemName}): place it ${item.placement}.`;
  }).join("\n");

  return `You are editing the provided room/space photo.

Add the following items to the photo naturally. Each item is shown in the reference images provided alongside this prompt — use them as visual references for what each product looks like:

${itemDescriptions}

Important rules:
- Preserve all existing furniture, structures, and elements in the photo exactly as they are.
- Respect the existing lighting direction and shadow angles.
- Respect perspective and scale — objects must look the correct size for the space.
- The new items should look like they were always there, not composited on top.
- Clean, seamless edges around all new objects.
- Do not change the aspect ratio of the image.
- Do not add watermarks, labels, or text overlays.
- The result should look like a real photograph, not a rendering.

The space is a ${sceneAnalysis.spaceType}.`;
}
```

### About passing product images to Nano Banana
Your existing Nano Banana wrapper currently accepts one image + one prompt. You need to check whether it supports passing multiple reference images. The Gemini 2.5 Flash Image API supports up to 14 reference images in one call.

**If your wrapper supports multiple images:** pass `[userPhoto, product1Image, product2Image, ...]` as the image array.

**If your wrapper only supports one image today:** you have two options:
- Option A (recommended for v1): Only pass the room photo. The text prompt alone with rich product descriptions is good enough for a first version. Add multi-image support as a v2 improvement.
- Option B: Fetch each product image URL, convert to base64, and extend the wrapper to accept an array. See the image fetching note below.

### Fetching product images for the API call
Product images from SerpAPI come as URLs. To pass them to Gemini, you need to either:
- Pass the URL directly if the Gemini API accepts image URLs (check your wrapper — it may already handle this)
- Or fetch + convert to base64:

```js
async function urlToBase64(url) {
  // Must be done server-side or via a proxy to avoid CORS
  const response = await fetch(url);
  const blob = await response.blob();
  return new Promise((resolve) => {
    const reader = new FileReader();
    reader.onload = () => resolve({
      base64: reader.result.split(",")[1],
      mediaType: blob.type,
    });
    reader.readAsDataURL(blob);
  });
}
```

> **CORS WARNING:** Fetching product images from Amazon/IKEA/Target directly from the browser will almost always be blocked by CORS. You need a small backend route (e.g. a Next.js API route, Express endpoint, or serverless function) that acts as a proxy: it receives the image URL, fetches it server-side, and returns the base64 data. Build this proxy before attempting multi-image mode.

---

## Step F — Call Nano Banana

### What this step does
Call your existing Nano Banana wrapper with the room photo and the prompt built in Step E. Optionally pass product reference images if your wrapper supports it.

```js
async function generateAfterPhoto(userPhoto, prompt, productImages = []) {
  // This calls your existing Nano Banana wrapper
  // Signature: nanaBanana(photo, prompt, referenceImages?)
  const result = await nanaBanana(userPhoto, prompt, productImages);
  return result; // Returns a URL or blob of the generated image
}
```

Set `appState.status = "generating"` when this call starts. Show a loading state with a message like "Generating your upgraded space..." — this call takes 5–15 seconds.

---

## Step G — Results UI

### What to render
This is the final screen. It has two sections:

**Section 1 — Before / After**
- Two photos side by side (or stacked on mobile): the original photo and the Nano Banana result
- Label them "Before" and "After"
- Optional: a slider that reveals the after photo progressively (nice UX touch, not required for v1)

**Section 2 — Shopping List**
- Render a card for each `SelectedProduct`:
  - Product image (thumbnail from `chosenProduct.imageUrl`)
  - Product title
  - Price (bold)
  - Store badge (e.g. "Amazon", "IKEA")
  - Star rating if available
  - A prominent **"Buy on [Store]"** button that links to `chosenProduct.buyLink` — opens in new tab
- Below all cards: total estimated cost

**Note about the after photo:** Make it clear visually (small label or tooltip) that the generated image is an AI preview. The actual products may look slightly different. This sets the right expectation.

---

## Complete Orchestration Function

This is the main function that wires everything together. Call this when the user submits their photo and prompt.

```js
async function runRoomUpgrade(userInput) {
  // Parse budget from the prompt if not explicitly provided
  const budget = userInput.budget ?? parseBudget(userInput.prompt) ?? 100;

  try {
    // STEP A
    updateStatus("analyzing");
    updateStatusMessage("Analyzing your space...");
    const sceneAnalysis = await analyzeScene({ ...userInput, budget });

    // STEP B
    updateStatus("searching");
    updateStatusMessage("Finding products for your space...");
    const searchResults = await Promise.all(
      sceneAnalysis.shoppingList.map((item) => searchWithFallback(item))
    );

    // STEP C
    updateStatusMessage("Optimizing your budget...");
    const selectedProducts = await optimizeBudget(searchResults, budget);

    // STEP D — Show approval UI, wait for user to click "Generate"
    updateStatus("awaiting_approval");
    setSelectedProducts(selectedProducts);
    // Execution pauses here until the user clicks "Generate my upgrade →"
    // That button calls continueToGeneration()

  } catch (err) {
    updateStatus("error");
    setErrorMessage("Something went wrong during analysis. Please try again.");
    console.error(err);
  }
}

async function continueToGeneration(userInput, selectedProducts, sceneAnalysis) {
  try {
    // STEP E
    const prompt = buildNanaBananaPrompt(selectedProducts, sceneAnalysis);

    // STEP F
    updateStatus("generating");
    updateStatusMessage("Generating your upgraded space (this takes ~10 seconds)...");
    
    // For v1, pass only the room photo — no product reference images yet
    const afterPhotoUrl = await generateAfterPhoto(userInput.photo, prompt);

    // STEP G
    updateStatus("done");
    setAfterPhoto(afterPhotoUrl);

  } catch (err) {
    updateStatus("error");
    setErrorMessage("Image generation failed. Please try again.");
    console.error(err);
  }
}
```

---

## Budget Parser (Helper)

Extract the dollar amount from the user's free-text prompt.

```js
function parseBudget(prompt) {
  // Match patterns like "$100", "100 dollars", "100$", "hundred dollars"
  const dollarMatch = prompt.match(/\$\s*(\d+)/);
  if (dollarMatch) return parseInt(dollarMatch[1]);
  
  const wordMatch = prompt.match(/(\d+)\s*(dollars|bucks|usd)/i);
  if (wordMatch) return parseInt(wordMatch[1]);
  
  return null; // Return null if no budget found — prompt the user to clarify
}
```

If `parseBudget` returns null, show a small inline prompt asking "What's your budget?" before proceeding.

---

## Loading States — What to Show the User

The user is waiting across 3 separate API calls (Claude vision, product search, Claude budget optimizer, Nano Banana). Show meaningful progress, not a spinner.

| Status | Message to show |
|---|---|
| `analyzing` | "Analyzing your space..." |
| `searching` | "Finding X products for your space..." (update count as searches complete) |
| `optimizing` | "Putting together the best combination under $[budget]..." |
| `awaiting_approval` | Show product cards — no loading |
| `generating` | "Generating your upgraded space... (usually 10–15 seconds)" |
| `done` | Show results |
| `error` | Show error message + "Try again" button |

---

## File / Folder Structure

Place new code in the following locations (adapt to your existing project structure):

```
src/
  lib/
    analyzeScene.js        ← Step A (Claude Vision call)
    searchAllProducts.js   ← Step B (calls existing Stage 3)
    optimizeBudget.js      ← Step C (Claude text call)
    buildPrompt.js         ← Step E (prompt construction)
    parseBudget.js         ← Budget parser helper
  
  components/
    UploadForm.jsx          ← Already exists (Stage 1) — reuse
    ProductApprovalList.jsx ← Step D UI
    BeforeAfterView.jsx     ← Step G UI (before/after photos)
    ShoppingCard.jsx        ← Step G UI (individual product card)
    LoadingStatus.jsx       ← Progress messages
  
  pages/ (or app/ if Next.js)
    index.jsx              ← Main orchestration, holds AppState
  
  api/ (if Next.js, or a separate backend route)
    imageProxy.js          ← CORS proxy for fetching product images server-side
```

---

## Environment Variables Needed

```
ANTHROPIC_API_KEY=sk-ant-...         # For Steps A and C (Claude calls)
GOOGLE_GEMINI_API_KEY=...            # Already configured for Nano Banana
SERPAPI_KEY=...                      # Already configured for Stage 3
```

---

## v1 Scope — What to Build Now vs Later

### Build now (v1)
- Steps A through G as described above
- Product approval UI (Step D)
- Before/after display
- Budget parser
- Basic error handling + loading states

### Skip for v1, add later
- **Multi-image product reference passing to Nano Banana** — text-only prompt is good enough for v1
- **CORS proxy for product images** — only needed for multi-image mode
- **Product swap UI** — let users swap individual products before generating
- **Iterative refinement** — let users re-run the generation with a modified prompt
- **Save/share results** — export the before/after as a single image

---

## Known Gotchas and How to Handle Them

**1. Claude returns malformed JSON**
Always wrap `JSON.parse()` in a try/catch. If it fails, retry the API call once with an explicit instruction: "Your previous response was not valid JSON. Return ONLY the JSON object, no other text."

**2. SerpAPI returns products with missing images**
Filter out any product where `imageUrl` is null or empty before passing to the UI or Nano Banana.

**3. Nano Banana generates something weird**
This happens occasionally. Add a "Regenerate" button on the results screen that re-calls Step F with the same inputs. Do not re-run Steps A–C.

**4. Budget exceeds total after real prices**
In Step C's fallback logic: if no combination fits under budget, show the user a warning "We found the best options but they add up to $X — slightly over your $Y budget. Want to continue?" Don't silently generate.

**5. The user's photo is too large**
Gemini 2.5 Flash Image accepts images up to 7MB. If the uploaded file is larger, resize it client-side before sending. Use a canvas-based resize:

```js
async function resizeImageIfNeeded(file, maxSizeMB = 5) {
  if (file.size <= maxSizeMB * 1024 * 1024) return file;

  const img = new Image();
  const url = URL.createObjectURL(file);
  img.src = url;
  await new Promise((resolve) => (img.onload = resolve));

  const canvas = document.createElement("canvas");
  const scale = Math.sqrt((maxSizeMB * 1024 * 1024) / file.size);
  canvas.width = img.width * scale;
  canvas.height = img.height * scale;
  canvas.getContext("2d").drawImage(img, 0, 0, canvas.width, canvas.height);

  return new Promise((resolve) =>
    canvas.toBlob((blob) => resolve(new File([blob], file.name, { type: "image/jpeg" })), "image/jpeg", 0.9)
  );
}
```

---

## Testing Checklist (Do This Before Considering It Done)

- [ ] Upload a living room photo + "$100 budget" — verify the shopping list makes sense for the space
- [ ] Upload a backyard photo + "make this look better for $150" — verify budget parsing works
- [ ] Upload a photo + no budget mention — verify the budget clarification prompt appears
- [ ] Check that all product links actually open the correct product on Amazon/IKEA/Target
- [ ] Verify the before/after photos are both visible and labeled correctly
- [ ] Check loading states transition correctly through all 5 stages
- [ ] Test the "Regenerate" button on the results screen
- [ ] Test with a very large image (>5MB) — verify client-side resize works
- [ ] Test with a photo where Claude returns malformed JSON — verify retry logic works
- [ ] Test on mobile — verify the layout is usable on a narrow screen