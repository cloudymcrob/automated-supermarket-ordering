# Automated Supermarket Ordering

Python utilities that power a weekly supermarket shopping workflow — recipe scoring, ingredient aggregation, pantry deduction, and shopping list generation. Designed to be orchestrated by a Claude Code slash command (`/weekly-shop`) that ties together Notion databases, Tesco browser automation, and Slack notifications.

## Setup

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
# Install dependencies and create virtualenv
uv sync --group dev
```

## Usage

The modules are used as a library by the `/weekly-shop` Claude Code command. They can also be run standalone:

```bash
uv run python -m shopping.<module>
```

### Modules

| Module | Purpose |
|--------|---------|
| `models` | Domain dataclasses — `Recipe`, `RecipeIngredient`, `PantryItem`, `ShoppingListItem`, `RegularItem`, `ScoredRecipe`, `MealPlanEntry` |
| `ingredients` | Ingredient parsing, unit conversion (via [Pint](https://pint.readthedocs.io/)), and aggregation across recipes |
| `meal_planning` | Recipe scoring (recency, pantry overlap, cuisine variety, rating, simplicity) and weekly meal selection |
| `pantry` | Subtract pantry inventory from needed ingredients with unit-aware deduction |
| `shopping_list` | Format the final shopping list, check regular recurring items, and estimate budget |

## Tests

```bash
uv run pytest
```

## Project Structure

```
src/shopping/        # Main package
  models.py          # Domain models and enums
  ingredients.py     # Parsing and aggregation
  meal_planning.py   # Recipe scoring and selection
  pantry.py          # Pantry deduction logic
  shopping_list.py   # List formatting and regular items
data/
  unit_conversions.json  # Custom unit conversion mappings
tests/               # pytest test suite
.claude/
  commands/weekly-shop.md  # Claude Code slash command definition
```
