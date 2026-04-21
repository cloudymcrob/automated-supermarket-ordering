# Automated Supermarket Ordering

## Notion Data Source IDs

All databases live under [Automated Shopping](https://www.notion.so/Automated-Shopping-333768f38fe3803f8915d62bebcc4243).

| Database | Data Source ID |
|----------|---------------|
| Recipes | `collection://c484fc86-6058-4c7c-9c82-af7d9830b1db` |
| Order History | `collection://47c69634-05b4-4dd9-85f5-7cac12e64798` |
| Learnings | `collection://b1e318ba-3e4d-46d6-8749-ca166e60925c` |
| Recipe Ingredients | `collection://f59cef18-fcbf-448c-91f2-a8f2aada5b8d` |
| Pantry Inventory | `collection://8639fbc8-fd73-4933-8e29-24c4a7ae3d07` |
| Shopping Preferences | `collection://e9cccfe4-5e5a-45bc-815d-19ef94719e4e` |
| Regular Items | `collection://0d4931a0-e4bb-49ab-a81a-434f31812161` |

The **Order History** DB (formerly called "Meal Plans") is the single source of truth for each week's plan + order. Each row = one week, with properties for cost, item count, status, and feedback, plus page content containing the recipe table and per-recipe ingredient breakdown.

## Notes Columns

Two databases have a **Notes** rich text column for contextual learnings:

| Database | Notes Purpose |
|----------|--------------|
| Recipes | Recipe-level feedback (e.g. "too spicy", "great for batch cooking") |
| Recipe Ingredients | Recipe-specific ingredient adjustments (e.g. "double the garlic here") |

Notes are date-prefixed (e.g. `[2026-04-03] Too spicy — reduce chili`).

General ingredient/brand knowledge (e.g. "avoid own-brand yoghurt", "frozen spinach better value") lives in the **Shopping Preferences** DB. The **Learnings DB** is for general workflow preferences only (e.g. "~150g meat per serving", "prefer more fish").

## Sub-Agent Architecture

The `/weekly-shop` skill uses sub-agents for each phase. Agent prompts live in `.claude/agents/`:

| Agent | File | Purpose |
|-------|------|---------|
| Recipe Sync | `recipe-sync.md` | Populate missing recipe ingredients/instructions from source URLs |
| Recipe Scorer | `recipe-scorer.md` | Score and rank recipes, return top candidates |
| Ingredient Calc | `ingredient-calc.md` | Aggregate ingredients programmatically, deduct pantry, sanity-check |
| Tesco Basket | `tesco-basket.md` | Add items to Tesco basket via Chrome automation |
| Basket Verifier | `basket-verifier.md` | Independent check that basket matches expected list |
| Google Keep Reader | `google-keep-reader.md` | Read unchecked items from household shopping list |
| DB Updater | `db-updater.md` | Update all Notion databases with workflow results and feedback |

## Cooking Efficiency & Portion Model

Every recipe has a **Cook Style** (Quick ≤40 min / Batch / Both) and two scaling fields:

| Field | Default | Meaning |
|-------|---------|---------|
| `Quantity Multiplier` | 1.0 | Multiplies the recipe's stated ingredient amounts |
| `Num Portions Per Quantity` | servings / 1.5 | Portions produced at multiplier=1 (adjusted via feedback) |

- **Total portions** = `num_portions_per_quantity × quantity_multiplier`
- **Meals covered** = `total_portions / 2` (for 2 people)
- **Ingredient scaling** = recipe amounts × `quantity_multiplier`

Typical week: 1-2 batch cooks (×2-3 multiplier, covers 3-4 days each) + quick meals for remaining days. Target ~3-5 cooking sessions, not 10.

## Household Profile

- 2 people, large portions (~1.5x recipe servings)
- Min 50g protein per serving
- **~150g meat per serving when meat is the main source of protein** (overrides older 200g guideline)
- Allergies: nuts, coconut, poppy seeds (direct ingredients only; "may contain" is fine)
- Budget: ~£50/week, prefer value options
- Lunches: batch-cooked for office days, or very quick
- Dinners: mix of batch cooks and quick meals

## Python Utilities

Run from project root: `python3 -m shopping.<module>`

- `src/shopping/models.py` — domain dataclasses
- `src/shopping/ingredients.py` — unit conversion, aggregation, parsing
- `src/shopping/pantry.py` — pantry deduction logic
- `src/shopping/meal_planning.py` — recipe selection scoring
- `src/shopping/shopping_list.py` — formatting, regular items check
