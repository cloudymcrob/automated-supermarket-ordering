---
name: weekly-shop
description: Run the weekly supermarket shopping workflow — selects recipes, calculates ingredients, checks pantry, builds a Tesco basket via Chrome browser automation, reads the Google Keep shopping list, and sends a Slack review DM. Use this skill whenever the user says "weekly shop", "do the shopping", "meal plan", "what should we cook this week", "what's for dinner", "order groceries", "Tesco order", "shopping list", "grocery list", "plan meals", "do the Tesco shop", or anything related to planning meals and ordering groceries for the week. Also trigger when the user mentions specific phases like "add items to Tesco", "check the pantry", "what do we need from the shops", or "build the basket". Even casual prompts like "food for next week?" or "can you sort the shopping" should trigger this skill.
---

You are running the weekly supermarket shopping workflow for Robbie.

This workflow has 8 phases. If the user specifies a phase to start from (e.g. "start from Phase 5"), skip to that phase. Otherwise, start from Phase 1.

## Household Profile

- 2 people, large portions
- Default servings multiplier: 1.5x (override with Actual Portions from recipe if available)
- Minimum 50g protein per serving; ~200g meat per serving if protein is mainly from meat
- **Allergies**: nuts, coconut, poppy seeds — check direct ingredients only. "May contain" warnings are fine.
- Budget: ~£50/week. Prefer value/own-brand Tesco options unless preferences say otherwise.
- Lunches: simple, quick (under 15-30 mins), high protein, no-cook or quick-cook
- Dinners: main planned meals, more variety allowed

## Notion Data Sources

Use `mcp__792c926c-2a2b-479f-8cd0-5959ff5aebc2__notion-query-data-sources` to query and `mcp__792c926c-2a2b-479f-8cd0-5959ff5aebc2__notion-create-pages` / `mcp__792c926c-2a2b-479f-8cd0-5959ff5aebc2__notion-update-page` to write.

| Database | Data Source ID |
|----------|---------------|
| Ingredients | `collection://c335d5eb-d770-40e7-8386-fea913fa5f74` |
| Recipes | `collection://c484fc86-6058-4c7c-9c82-af7d9830b1db` |
| Meal Plans | `collection://47c69634-05b4-4dd9-85f5-7cac12e64798` |
| Learnings | `collection://b1e318ba-3e4d-46d6-8749-ca166e60925c` |
| Recipe Ingredients | `collection://f59cef18-fcbf-448c-91f2-a8f2aada5b8d` |
| Pantry Inventory | `collection://8639fbc8-fd73-4933-8e29-24c4a7ae3d07` |
| Meal Plan Entries | `collection://a16f20fc-a485-4f7d-8199-378cc6d65edc` |
| Shopping Preferences | `collection://e9cccfe4-5e5a-45bc-815d-19ef94719e4e` |
| Regular Items | `collection://0d4931a0-e4bb-49ab-a81a-434f31812161` |
| Order History | `collection://f0d2230e-73d9-4ace-a302-01415a50c8cc` |

## Python Utilities

These live in `src/shopping/` within the project. Run via Bash from the project root.

- `models.py` — `Recipe` (has `meal_types: list[MealType]`, `servings_multiplier` property, `contains_allergen()` method), `RecipeIngredient`, `PantryItem`, `ShoppingListItem`, `RegularItem`, `ScoredRecipe`, `MealPlanEntry`
- `ingredients.py` — `parse_ingredient_line(text) -> RecipeIngredient`, `aggregate_ingredients(recipe_ingredients, servings_multiplier) -> list[AggregatedIngredient]`
- `pantry.py` — `deduct_pantry(needed, pantry) -> list[ShoppingListItem]`, `update_pantry_after_cooking(pantry, used) -> list[PantryItem]`
- `meal_planning.py` — `score_recipes(recipes, pantry, recent_recipe_names, today) -> list[ScoredRecipe]`, `select_weekly_meals(scored_recipes, num_dinners=5, num_lunches=5) -> dict[str, list[ScoredRecipe]]` (returns `{"dinners": [...], "lunches": [...]}`)
- `shopping_list.py` — `check_regular_items(regular_items, today) -> list[RegularItem]`, `format_shopping_list(items, group_by_category) -> str`, `estimate_budget(items) -> str`

## Slack

Robbie's Slack user ID is `U093RE9TDV4`. DM him directly without needing to look up the ID.

---

## Phase 1: Recipe Selection

**Goal**: Choose ~5 dinners and ~5 lunches for the week.

### Step 1a: Load context

Query the Learnings DB for all active learnings — these are preferences and feedback from previous weeks that should influence your selections:

```sql
SELECT * FROM "collection://b1e318ba-3e4d-46d6-8749-ca166e60925c"
WHERE "Active" = '__YES__'
```

Read and internalise all learnings before proceeding.

### Step 1b: Get recipes and recent history

Query active recipes:
```sql
SELECT * FROM "collection://c484fc86-6058-4c7c-9c82-af7d9830b1db"
WHERE "Active" = '__YES__'
```

Query recent meal plan entries (last 3 weeks) to avoid repeats:
```sql
SELECT * FROM "collection://a16f20fc-a485-4f7d-8199-378cc6d65edc"
ORDER BY createdTime DESC LIMIT 30
```

### Step 1c: Score and select

**Converting Notion data to Python objects**: The Notion `Meal Type` field is a multi-select stored as a JSON string like `["Dinner"]` or `["Lunch", "Dinner"]`. When constructing `Recipe` objects, parse this with `json.loads()` and map to `MealType` enum values. Similarly, `Tags` is a JSON array of strings. The `Rating` field is a select stored as a string ("1" through "5") — convert to `int`. The `Active` field uses `"__YES__"` / `"__NO__"`.

Use the Python scoring utility to rank recipes. The scorer considers:
- Recipes not cooked recently (0-30 points)
- Recipes that use ingredients already in the pantry (0-20 points)
- Cuisine variety across the week (0-10 points)
- Higher-rated recipes (0-15 points)
- Quick/simple recipes for lunch slots (0-10 points)

It automatically filters out recipes containing allergen keywords.

`select_weekly_meals()` returns `{"dinners": [...], "lunches": [...]}`. It uses a 4-pass strategy: dinner-only recipes first, then lunch-only, then dual-type recipes fill whichever slot needs more, then any remaining slots get the best remaining recipes.

### Step 1d: Present to user

Present your suggestions in a clear format:

```
**Dinners**
- Monday: Chicken Stir Fry (last cooked 3 weeks ago, uses pantry rice)
- Tuesday: Beef Bolognese (highly rated, batch cook potential)
...

**Lunches**
- Monday-Friday: Quick Chicken Wraps (10 min, high protein)
...
```

**WAIT FOR USER CONFIRMATION.** The user may swap recipes, add constraints, or approve as-is.

### Step 1e: Create meal plan in Notion

After confirmation, create a new Meal Plan entry and individual Meal Plan Entries for each day/meal.

---

## Phase 2: Ingredient Calculation

**Goal**: Aggregate all ingredients needed across every selected recipe.

### Step 2a: Get recipe ingredients

Query Recipe Ingredients for each selected recipe:
```sql
SELECT * FROM "collection://f59cef18-fcbf-448c-91f2-a8f2aada5b8d"
WHERE "Recipe" LIKE '%<recipe_page_url>%'
```

**If a recipe has no ingredients in the DB** (this is common — many recipes were imported without ingredient data), check if the recipe has a `Source URL`. If it does, use `mcp__Claude_in_Chrome__navigate` and `mcp__Claude_in_Chrome__get_page_text` to fetch the recipe page and extract the ingredient list. Use `parse_ingredient_line()` to parse each ingredient. Then save the parsed ingredients back to the Recipe Ingredients DB so they're available for future runs.

If there's no Source URL either, ask the user for the ingredient list or skip the recipe.

### Step 2b: Aggregate

Use the Python `aggregate_ingredients()` function to:
- Normalise units (g, ml, whole, etc.)
- Sum quantities across all recipes
- Apply servings multiplier (check each recipe's "Actual Portions" field — if set, use `3.0 / actual_portions` as multiplier; otherwise default to 1.5x)

### Step 2c: Check regular items

Query Regular Items DB for items due:
```sql
SELECT * FROM "collection://0d4931a0-e4bb-49ab-a81a-434f31812161"
WHERE "Auto Add" = '__YES__'
```

Use `check_regular_items()` to determine which are due based on frequency and last ordered date. Add due items to the ingredient list.

### Step 2d: Output

Present the complete ingredient list grouped by category.

---

## Phase 3: Pantry Check

**Goal**: Subtract what's already in the house from what's needed.

### Step 3a: Get pantry inventory

```sql
SELECT * FROM "collection://8639fbc8-fd73-4933-8e29-24c4a7ae3d07"
WHERE "Status" != 'Out' AND "Status" != 'Expired'
```

### Step 3b: Deduct

Use `deduct_pantry()` to subtract pantry quantities from needed quantities. This handles unit conversion (e.g. 500g pantry rice vs 1.5kg needed = 1kg to buy).

### Step 3c: Generate shopping list

The output is the "need to buy" list — only items where the needed quantity exceeds what's in the pantry.

---

## Phase 4: Human Verification

**Goal**: Confirm pantry assumptions and finalise the shopping list before ordering.

Present to the user:

```
**Pantry assumptions** (please correct any that are wrong):
- Rice: I think you have 500g → need 1.5kg → buying 1kg ✓
- Olive oil: I think you have a full bottle → not buying ✓
- Chicken breast: not in pantry → buying 900g

**Shopping list** (X items):
[formatted list grouped by category]

**Budget estimate**: ~£XX (target: £50)

Does this look right? Please correct any wrong pantry assumptions.
```

**WAIT FOR USER RESPONSE.** Apply any corrections:
- Update Pantry Inventory in Notion for corrected items
- Recalculate the shopping list if pantry quantities changed

---

## Phase 5: Tesco Basket Building

**Goal**: Add all shopping list items to the Tesco online basket.

### Step 5a: Open Tesco and check login

Use `mcp__Claude_in_Chrome__navigate` to go to `https://www.tesco.com/groceries/`.

Use `mcp__Claude_in_Chrome__read_page` to check if the user is logged in (look for "Sign out" or "My account" in the nav, or a greeting like "Hello Robert"). If not logged in:

1. Click "Sign in"
2. Enter email `robbiemcleod10@hotmail.co.uk` and click Next
3. On the password page, scroll down and click **"Sign in with One-time code"**
4. Tesco sends a 6-digit code to the email
5. Open Outlook (`https://outlook.live.com/mail/`) in a new tab to retrieve the code
6. Enter the code on the Tesco page and submit
7. Verify login succeeded (look for "Hello Robert" or "Sign out")

### Step 5b: Dismiss any popups

After navigating to Tesco, check for and dismiss any cookie consent banners or promotional popups that might block interaction. Use `mcp__Claude_in_Chrome__find` to look for "Accept" or "Close" buttons on overlays.

### Step 5c: Check preferences

Before searching for each item, query Shopping Preferences:
```sql
SELECT * FROM "collection://e9cccfe4-5e5a-45bc-815d-19ef94719e4e"
WHERE "Item" = '<ingredient_name>'
```

Use the Tesco Search Term if available; otherwise search by ingredient name.

### Step 5d: Add items to basket

For each shopping list item:

1. **Search**: Click the search bar, clear any previous text, type the search term, press Enter. Wait for results to load.

2. **Select product**: Use `mcp__Claude_in_Chrome__read_page` to read search results. Choose the best product considering:
   - Preferred brand from Shopping Preferences (if set)
   - Price sensitivity (default: Cheapest / value options)
   - Closest quantity match to what's needed (avoid waste)
   - Compare £/kg or £/unit prices, not just headline prices
   - Avoid "out of stock" items

3. **Add to basket**: Find and click the "Add" button for the chosen product. If you need more than 1, use the "+" button to increase quantity.

4. **Verify**: Check the basket total in the top-right corner updated.

Add a ~2 second wait between items to avoid overwhelming the page.

Track which items succeeded and which failed (not found / out of stock).

### Step 5e: Review basket

Navigate to the basket page. Use `mcp__Claude_in_Chrome__get_page_text` to capture the basket summary including items and total price.

Report any items that couldn't be found or were out of stock.

---

## Phase 6: Google Keep Extras

**Goal**: Check for additional items on the Google Keep shopping list.

### Step 6a: Open Google Keep

Use `mcp__Claude_in_Chrome__navigate` to go to `https://keep.google.com/`.

### Step 6b: Find shopping list

Use `mcp__Claude_in_Chrome__read_page` to locate the **"Household shopping list"** note (it's pinned and shared with anna main). Read the unchecked items — these are the items that need buying.

### Step 6c: Present and add items

Present the Keep items to the user and ask which to add. For confirmed items:
- Search on Tesco and add to basket (same flow as Phase 5)

### Step 6d: Confirm

**WAIT FOR USER CONFIRMATION.** Tell the user what Keep items were found and added.

---

## Phase 7: Slack Review

**Goal**: Send the user a summary for final review before checkout.

### Step 7a: Compile summary

Build a message containing:
- This week's meal plan (dinners + lunches by day)
- Full basket contents with quantities and prices (from the Tesco basket)
- Any items that couldn't be found
- Estimated total vs budget
- Regular items included

### Step 7b: Send to Robbie

Use `mcp__659504af-dc5f-4c06-81db-d846567cc8ef__slack_send_message` to DM Robbie at user ID `U093RE9TDV4`:

```
🛒 *Weekly Shop — w/c [date]*

*🍽️ Dinners*
• Mon: [recipe] _(cuisine)_
...

*🥗 Lunches*
• [recipe] _(tags)_
...

*🛒 Basket Summary*
[X] items | Est. £[total] (budget: £50)
[list any missing/out-of-stock items]

✅ _Reply with changes or "looks good" to proceed._
```

### Step 7c: Process feedback

If the user responds with changes (in the current conversation or via Slack):
- Apply substitutions/removals/additions on Tesco via Chrome MCP
- Record any preference feedback:
  - Brand preferences → update Shopping Preferences DB
  - Dish likes/dislikes → create Learnings entry
  - Portion feedback → update Actual Portions in Recipes DB

---

## Phase 8: Finalize

**Goal**: Wrap up and update all tracking databases.

### Step 8a: Confirm ready

Tell the user: "Your basket is ready for checkout. I've left the Tesco tab open — you can choose a delivery slot and place the order."

### Step 8b: Update databases

1. **Order History**: Create new entry with date, item count, estimated total, status = "Draft"
2. **Pantry Inventory**: Add ordered items (expected to arrive), deduct items that will be used by the meal plan
3. **Regular Items**: Update "Last Ordered" date for any regular items included
4. **Recipes**: Update "Last Cooked" date and increment "Times Cooked" for selected recipes
5. **Meal Plan**: Set status to "Active"

### Step 8c: Portion follow-up reminder

After the meals are cooked during the week, follow up to ask: "How many portions did [recipe] actually make?" Update the Actual Portions field in the Recipes DB and create a Portion Feedback learning in the Learnings DB.

---

## Error Handling

- **Tesco not logged in**: Use the OTP flow described in Phase 5a. If that fails, ask the user to log in manually.
- **Product not found**: Log it, continue with remaining items, report at the end.
- **Chrome MCP unavailable**: Skip browser phases, output the shopping list for manual use.
- **Notion query fails**: Retry once, then report the error and continue with available data.
- **Budget significantly over**: Flag it during Phase 4 verification and suggest substitutions.
- **Recipe has no ingredients**: Fetch from Source URL if available, or ask the user.
