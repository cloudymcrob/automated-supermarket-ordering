---
name: sync-recipes
description: Sync recipe ingredients and instructions from source URLs into Notion. Checks which recipes are missing data, fetches their source pages, parses ingredients and instructions, and stores them in the database. Use when the user says "sync recipes", "import recipes", "fetch recipe data", "populate ingredients", "pull recipe ingredients", or anything about backfilling recipe data from URLs.
---

You are running the recipe sync workflow — populating the Recipe Ingredients database and recipe Instructions from source URLs.

## Notion Data Sources

Use `mcp__792c926c-2a2b-479f-8cd0-5959ff5aebc2__notion-query-data-sources` to query and `mcp__792c926c-2a2b-479f-8cd0-5959ff5aebc2__notion-create-pages` / `mcp__792c926c-2a2b-479f-8cd0-5959ff5aebc2__notion-update-page` to write.

| Database | Data Source ID |
|----------|---------------|
| Recipes | `collection://c484fc86-6058-4c7c-9c82-af7d9830b1db` |
| Recipe Ingredients | `collection://f59cef18-fcbf-448c-91f2-a8f2aada5b8d` |
| Ingredients | `collection://c335d5eb-d770-40e7-8386-fea913fa5f74` |

## Python Utilities

Run via `uv run python3 -c "..."` from the project root.

- `ingredients.py` — `parse_ingredient_line(text) -> RecipeIngredient`, `standardize_for_storage(qty, unit) -> (qty, unit)`

## Canonical Storage Format

All ingredient quantities must be stored in metric:
- **Weights**: g (or kg if >= 1000g)
- **Volumes**: ml (or l if >= 1000ml), except tsp/tbsp which are preserved as-is
- **Countable units**: whole, can, clove, tin, pack, etc. — preserved as-is

Use `standardize_for_storage()` after parsing each ingredient line to normalise before saving to Notion.

## Allergens

- **Allergies**: nuts, coconut, poppy seeds — flag any recipes containing these but still sync them (the weekly-shop skill handles exclusion at selection time)

---

## Phase 1: Discover Recipes Needing Sync

### Step 1a: Get all active recipes

```sql
SELECT * FROM "collection://c484fc86-6058-4c7c-9c82-af7d9830b1db"
WHERE "Active" = '__YES__'
```

### Step 1b: Check which recipes have ingredients already

For each recipe that has a `Source URL`, query the Recipe Ingredients DB:

```sql
SELECT * FROM "collection://f59cef18-fcbf-448c-91f2-a8f2aada5b8d"
WHERE "Recipe" LIKE '%<recipe_page_url>%'
```

### Step 1c: Build the sync list

Categorise each recipe with a Source URL into:
- **Needs ingredients**: no entries in Recipe Ingredients DB
- **Needs instructions**: no Instructions text on the Recipe page
- **Needs both**: missing both
- **Complete**: has both — skip

Recipes **without** a Source URL are skipped entirely.

### Step 1d: Report to user

Present the list:

```
Found X recipes needing sync:
- [Recipe Name] — needs ingredients + instructions
- [Recipe Name] — needs ingredients only
- [Recipe Name] — needs instructions only

Y recipes already complete. Z recipes skipped (no Source URL).

Proceed?
```

**WAIT FOR USER CONFIRMATION** before fetching any pages.

---

## Phase 2: Fetch & Parse

For each recipe needing sync, process one at a time:

### Step 2a: Fetch the page

1. **Try `WebFetch` first** — use the Source URL directly. This is faster and doesn't require the browser.
2. **If WebFetch fails** (returns an error, empty content, or the page blocks automated access), **fall back to Chrome MCP**:
   - Use `mcp__Claude_in_Chrome__navigate` to open the Source URL
   - Use `mcp__Claude_in_Chrome__get_page_text` to extract the page content
3. If **both** WebFetch and Chrome MCP fail, log the failure and continue to the next recipe.

### Step 2b: Extract ingredients (if needed)

From the page content, identify the ingredients section. Recipe pages typically have a clearly labelled "Ingredients" heading followed by a list.

For each ingredient line:

1. Parse with `parse_ingredient_line()`:
   ```python
   from shopping.ingredients import parse_ingredient_line, standardize_for_storage
   ri = parse_ingredient_line("200g chicken breast, diced")
   qty, unit = standardize_for_storage(ri.quantity, ri.unit)
   # ri.ingredient_name = "chicken breast", qty = 200, unit = "g", ri.preparation = "diced"
   ```

2. Apply `standardize_for_storage()` to normalise the quantity and unit to canonical metric format.

3. Collect all parsed ingredients for this recipe.

**Validation**: If parsing yields fewer than 2 ingredients, flag the recipe for manual review — the extraction likely failed.

### Step 2c: Extract instructions (if needed)

From the page content, identify the method/instructions/directions section. Extract as numbered steps in plain text.

**Important**: Enrich each step with the standardised ingredient quantities from Step 2b. When a step references an ingredient, include the quantity so the instructions are self-contained. Use the standardised metric quantities (after `standardize_for_storage()`). Examples:

- Source says "fry the mince" → write "Fry all 500g of mince"
- Source says "add the onions" → write "Add the 2 onions, diced"
- Source says "pour in the stock" → write "Pour in 500ml of stock"
- Source says "season with salt" → write "Season with 1 tsp salt" (if quantity known) or "Season with salt to taste" (if no quantity)

```
1. Preheat the oven to 200C.
2. Dice the 2 onions and mince the 3 cloves of garlic.
3. Heat 1 tbsp oil in a large pan over medium heat.
4. Fry all 500g of chicken breast until golden.
...
```

Keep it concise — strip any ads, tips, or narrative padding. Just the cooking steps with quantities.

### Step 2d: Report progress

After each recipe: "Synced 3/12: [Recipe Name] — 8 ingredients, 6 steps"

---

## Phase 3: Write to Notion

For each successfully parsed recipe:

### Step 3a: Save ingredients

Create one Recipe Ingredient entry per ingredient in the Recipe Ingredients DB. Each entry should include:
- **Recipe**: relation to the recipe page
- **Ingredient**: the ingredient name
- **Quantity**: the standardised quantity (after `standardize_for_storage()`)
- **Unit**: the standardised unit
- **Preparation**: any prep notes (diced, minced, etc.)

### Step 3b: Save instructions

Update the Recipe page with the Instructions text using `mcp__792c926c-2a2b-479f-8cd0-5959ff5aebc2__notion-update-page`.

### Step 3c: Continue on failure

If writing to Notion fails for a recipe, log the error and continue with the next recipe. Do not abort the entire sync.

---

## Phase 4: Summary

Present a final report:

```
Sync complete:
- X recipes synced successfully (ingredients + instructions)
- Y recipes synced partially (ingredients only / instructions only)

Failed:
- [Recipe Name] — WebFetch and Chrome MCP both failed
- [Recipe Name] — only 1 ingredient parsed, needs manual review

Skipped:
- Z recipes with no Source URL
```

---

## Error Handling

- **WebFetch fails**: Fall back to Chrome MCP. Only skip if both fail.
- **Chrome MCP unavailable**: Report which recipes couldn't be fetched, suggest retrying when browser is available.
- **Parsing yields < 2 ingredients**: Flag for manual review, still save whatever was parsed.
- **Notion write fails**: Log and continue to next recipe.
- **Recipe page is paywalled or requires login**: Log as failure, suggest manual entry.
- **Python utility error**: If `parse_ingredient_line()` or `standardize_for_storage()` raises an error, fix the bug in the source file, run `uv run pytest` to confirm, and continue.

## Idempotency

This skill is safe to re-run. It skips recipes that already have both ingredients and instructions. To force a re-sync of a specific recipe, first delete its existing Recipe Ingredient entries in Notion, then re-run.
