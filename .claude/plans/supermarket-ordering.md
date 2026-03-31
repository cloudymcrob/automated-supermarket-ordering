# Automated Supermarket Ordering - Implementation Plan

## Context

Build a weekly shopping workflow orchestrated as a Claude Code skill (`/weekly-shop`) with Python utility functions for deterministic computation. Use the `anthropic-skills:skill-creator` skill to create and iterate on the skill definition.

The workflow: selects recipes -> calculates ingredients -> checks pantry -> builds a Tesco basket via browser automation -> integrates Google Keep -> gets human review via Slack -> user places order.

**Household**: 2 people, large portions (~1.5x recipe servings). Min 50g protein per serving; ~200g meat per serving if meat-based. Track actual portion yield per meal for future accuracy.

**Allergies**: Nuts, coconut, poppy seeds.

**Budget**: ~£50/week. Avoid expensive products except special occasions.

**Meals**: Dinners (main planned meals) + lunches (simple, quick, high protein -- stir fry, no-cook, etc.).

**Notion parent page**: https://www.notion.so/Automated-Shopping-333768f38fe3803f8915d62bebcc4243

**Communication**: Slack DM to Robbie directly.

---

## Architecture

### Data Storage: Notion (primary)
- All persistent data in Notion databases (recipes, pantry, preferences, orders, learnings)
- Claude accesses via Notion MCP
- Python utilities pull data into memory for computation, push results back

### Browser Automation: Chrome MCP
- Tesco + Google Keep via user's real browser (already logged in)
- Avoids credential management, bot detection

### Skill Creation: `anthropic-skills:skill-creator`
- Use the skill-creator to build `/weekly-shop` as a proper Claude Code skill
- Skill-creator handles: skill file structure, description optimization for triggering, eval setup
- Allows iterating on the skill with evals to verify it works correctly

### Preference Learning: Notion "Learnings" DB
- Records all learned preferences, feedback, portion data
- Skill reads all active learnings at start of each run
- User can browse/edit/delete in Notion

---

## Data Model (Notion Databases)

All under: [Automated Shopping](https://www.notion.so/Automated-Shopping-333768f38fe3803f8915d62bebcc4243)

| Database | Purpose | Key Fields |
|----------|---------|------------|
| **Recipes** | Master recipe list | Name, Cuisine, Meal Type, Servings, Actual Portions, Prep/Cook Time, Last Cooked, Times Cooked, Rating, Tags, Active |
| **Recipe Ingredients** | Junction: recipe -> ingredients | Recipe (relation), Ingredient (relation), Quantity, Unit, Preparation, Optional |
| **Ingredients** | Master ingredient list | Name, Category, Default Unit, Shelf Life, Staple flag, Aliases |
| **Pantry Inventory** | What's in the house | Ingredient (relation), Quantity, Unit, Expiry Date, Status, Location |
| **Meal Plans** | Weekly meal plan records | Week, Start Date, Status |
| **Meal Plan Entries** | Junction: plan -> recipes | Meal Plan (relation), Recipe (relation), Day, Meal, Servings Multiplier |
| **Shopping Preferences** | Brand/product preferences | Ingredient (relation), Preferred Brand, Tesco Search Term, Price Sensitivity |
| **Regular Items** | Recurring non-recipe purchases | Item, Frequency, Typical Quantity, Last Ordered, Next Due, Auto Add |
| **Order History** | Past order records | Date, Meal Plan (relation), Total Items, Total Cost, Feedback, Status |
| **Learnings** | Preference learning & feedback | Learning, Category, Source, Date, Active |

---

## Project Structure

```
automated-supermarket-ordering/
├── .claude/
│   ├── commands/
│   │   └── weekly-shop.md           # Main skill (created via skill-creator)
│   ├── CLAUDE.md
│   └── plans/
├── pyproject.toml                   # Dependencies (pint for units)
├── src/
│   └── shopping/
│       ├── __init__.py
│       ├── models.py                # Dataclasses
│       ├── ingredients.py           # Unit conversion, aggregation, parsing
│       ├── pantry.py                # Pantry deduction logic
│       ├── meal_planning.py         # Recipe selection scoring
│       └── shopping_list.py         # Shopping list formatting, regular items
├── tests/
│   ├── test_ingredients.py
│   ├── test_pantry.py
│   └── test_shopping_list.py
└── data/
    └── unit_conversions.json
```

---

## Workflow Phases (what the skill orchestrates)

### Phase 1: Recipe Selection
1. Load active learnings from Learnings DB
2. Query Recipes DB + recent Meal Plan Entries (last 2-3 weeks)
3. Run `meal_planning.py` to score/rank (recency, pantry overlap, variety, rating, allergen filtering)
4. **Human checkpoint**: present suggestions -> user confirms/swaps
5. Create Meal Plan + Entries in Notion

### Phase 2: Ingredient Calculation
1. Query Recipe Ingredients for selected recipes
2. Run `ingredients.py`: normalize units, aggregate, apply servings multiplier (default 1.5x, adjusted by Actual Portions)
3. Check Regular Items DB for due items
4. Output complete list

### Phase 3: Pantry Check
1. Query Pantry Inventory
2. Run `pantry.py`: subtract stock from requirements
3. Generate "need to buy" list

### Phase 4: Human Verification
- Present pantry assumptions + shopping list
- User corrects -> update Pantry in Notion
- Estimate total cost vs ~£50 budget

### Phase 5: Tesco Basket Building (Chrome MCP)
- Search + add each item, using Shopping Preferences for search terms/brands
- Default to value options; verify each add
- Report items not found / out of stock

### Phase 6: Google Keep Extras (Chrome MCP)
- Read shopping list note from keep.google.com
- Add items to Tesco basket

### Phase 7: Slack Review
- DM Robbie with meal plan + basket summary + estimated total
- Read feedback, apply changes on Tesco
- Record learnings

### Phase 8: Finalize
- Leave Tesco tab open for checkout
- Update Order History, Pantry, Regular Items, Recipe dates

---

## Implementation Steps

### Step 1: Foundation (Python utilities) -- DONE
- [x] Create project structure + `pyproject.toml` (dep: `pint`)
- [x] `src/shopping/models.py` -- dataclasses
- [x] `src/shopping/ingredients.py` -- unit conversion, aggregation, parsing
- [x] `src/shopping/pantry.py` -- deduction logic
- [x] `src/shopping/meal_planning.py` -- recipe scoring
- [x] `src/shopping/shopping_list.py` -- formatting, regular items check
- [x] Tests for ingredients, pantry, shopping_list (67 tests passing)
- [x] `data/unit_conversions.json`

### Step 2: Notion Databases -- DONE
- [x] Created all 10 databases under the Automated Shopping page (see CLAUDE.md for data source IDs)

### Step 3: Create Skill (via skill-creator) -- DONE
- [x] Created `/weekly-shop` skill at `.claude/commands/weekly-shop.md`
- [x] All 8 phases with detailed instructions
- [x] References to Python utilities
- [x] MCP tool usage patterns (Notion, Chrome, Slack)
- [ ] Run evals to verify skill triggers and follows workflow (deferred to Step 6)

### Step 4: Recipe Import -- DONE
- [x] Read Robbie's recipe list from Google Keep via Chrome MCP (opened "Cooked dishes" note, extracted all recipes)
- [x] Imported 67 recipes into Notion Recipes DB with cuisines, tags, source URLs, and notes
- [x] Includes fish dishes (fish removed from allergy list per user request)
- [ ] Recipe Ingredients import (deferred — will populate per-recipe as needed during weekly shop runs)

### Step 5: End-to-End Testing -- DONE
- [x] Unit tests: 78 passing (67 original + 11 integration tests)
- [x] Fixed `meal_type` → `meal_types` (list) to match Notion multi_select
- [x] Fixed `select_weekly_meals` to properly allocate dual-type recipes (lunch+dinner)
- [x] Notion integration: queried 67 recipes successfully, cuisine distribution verified
- [x] Notion → Recipe conversion: tested JSON parsing for Meal Type, Tags, etc.
- [x] Scoring + selection pipeline: verified with realistic 16-recipe test set
- [x] Tesco: signed in via OTP (one-time code to email), searched "chicken breast", added 1KG to basket (£6.85), removed — full add/remove cycle verified
- [x] Google Keep: read "Household shopping list" items (Peppers, Coriander, Chicken breast 1kg, etc.)
- [x] Slack: found Robbie (U093RE9TDV4), created test DM draft with meal plan summary format

### Step 6: Iterate with Skill Creator -- DONE
- [x] Reviewed skill description — expanded trigger phrases (added "what's for dinner", "grocery list", "plan meals", "sort the shopping", etc.)
- [x] Reviewed skill instructions against actual Python utility signatures
- [x] Added Tesco OTP login flow (Step 5a) — email + one-time code via Outlook
- [x] Added cookie/popup dismissal guidance (Step 5b)
- [x] Added Notion→Python object conversion guidance (JSON parsing for multi-selects, Rating, Active fields)
- [x] Documented `select_weekly_meals()` return format (`{"dinners": [...], "lunches": [...]}`)
- [x] Added fallback for recipes with no ingredients: fetch from Source URL via Chrome MCP
- [x] Hardcoded Robbie's Slack user ID (U093RE9TDV4) to skip lookup
- [x] Added Python utility function signatures with parameter types and return types
- [x] Improved Slack message template with structured format
- [x] Updated error handling: OTP flow for Tesco login, recipe ingredient fallback

---

## Verification

1. **Unit tests**: `pytest tests/` for ingredient aggregation, unit conversion, pantry deduction
2. **Notion integration**: verify all 10 databases queryable via Notion MCP
3. **Skill triggering**: verify `/weekly-shop` triggers correctly (via skill-creator evals)
4. **Recipe import**: import 3+ recipes from Google Keep, verify in Notion
5. **Tesco flow**: add 3 items to basket via Chrome MCP
6. **Full workflow**: run complete `/weekly-shop` for one week
