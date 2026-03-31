"""Ingredient parsing, unit conversion, and aggregation utilities."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import pint

from shopping.models import RecipeIngredient

# Global unit registry
_ureg = pint.UnitRegistry()

# Load conversion reference data
_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


def _load_conversions() -> dict:
    with open(_DATA_DIR / "unit_conversions.json") as f:
        return json.load(f)


_CONVERSIONS = _load_conversions()
_COUNTABLE = set(_CONVERSIONS["countable_units"])

# Canonical unit mapping: normalise variant spellings to a standard form
_UNIT_ALIASES: dict[str, str] = {
    "teaspoon": "tsp",
    "teaspoons": "tsp",
    "tablespoon": "tbsp",
    "tablespoons": "tbsp",
    "gram": "g",
    "grams": "g",
    "kilogram": "kg",
    "kilograms": "kg",
    "litre": "l",
    "litres": "l",
    "liter": "l",
    "liters": "l",
    "millilitre": "ml",
    "millilitres": "ml",
    "milliliter": "ml",
    "milliliters": "ml",
    "ounce": "oz",
    "ounces": "oz",
    "pound": "lb",
    "pounds": "lb",
    "cloves": "clove",
    "slices": "slice",
    "bunches": "bunch",
    "cans": "can",
    "tins": "tin",
    "packs": "pack",
    "packets": "pack",
    "packet": "pack",
    "bags": "bag",
    "rashers": "rasher",
    "fillets": "fillet",
    "breasts": "breast",
    "thighs": "thigh",
    "stalks": "stalk",
    "sticks": "stick",
    "sprigs": "sprig",
    "heads": "head",
    "sheets": "sheet",
    "balls": "ball",
    "pieces": "piece",
    "handfuls": "handful",
    "pinches": "pinch",
    "cups": "cup",
    "tsps": "tsp",
    "tbsps": "tbsp",
}


def canonicalize_unit(unit: str) -> str:
    """Normalise a unit string to its canonical form."""
    unit = unit.strip().lower()
    return _UNIT_ALIASES.get(unit, unit)


def is_weight_unit(unit: str) -> bool:
    return unit in _CONVERSIONS["weight_to_g"]


def is_volume_unit(unit: str) -> bool:
    return unit in _CONVERSIONS["volume_to_ml"]


def is_countable_unit(unit: str) -> bool:
    return unit in _COUNTABLE or unit == ""


def normalize_to_grams(quantity: float, unit: str) -> float | None:
    """Convert a weight quantity to grams. Returns None if not a weight unit."""
    factor = _CONVERSIONS["weight_to_g"].get(unit)
    if factor is None:
        return None
    return quantity * factor


def normalize_to_ml(quantity: float, unit: str) -> float | None:
    """Convert a volume quantity to ml. Returns None if not a volume unit."""
    factor = _CONVERSIONS["volume_to_ml"].get(unit)
    if factor is None:
        return None
    return quantity * factor


def units_compatible(unit_a: str, unit_b: str) -> bool:
    """Check if two units can be aggregated together."""
    a, b = canonicalize_unit(unit_a), canonicalize_unit(unit_b)
    if a == b:
        return True
    if is_weight_unit(a) and is_weight_unit(b):
        return True
    if is_volume_unit(a) and is_volume_unit(b):
        return True
    return False


def convert_to_common_unit(quantity: float, unit: str) -> tuple[float, str]:
    """Convert quantity to the best common unit (g for weight, ml for volume).

    Returns (converted_quantity, canonical_unit). If the unit is countable
    or unrecognised, returns it unchanged.
    """
    canon = canonicalize_unit(unit)

    grams = normalize_to_grams(quantity, canon)
    if grams is not None:
        if grams >= 1000:
            return grams / 1000, "kg"
        return grams, "g"

    ml = normalize_to_ml(quantity, canon)
    if ml is not None:
        if ml >= 1000:
            return ml / 1000, "l"
        return ml, "ml"

    return quantity, canon


def format_quantity(quantity: float, unit: str) -> str:
    """Format a quantity nicely for display."""
    if quantity == int(quantity):
        q_str = str(int(quantity))
    else:
        q_str = f"{quantity:.1f}"
    if unit and unit != "whole":
        return f"{q_str}{unit}"
    return q_str


# --- Ingredient line parsing ---

# Pattern: optional quantity (number or fraction), optional unit, ingredient name
_QUANTITY_PATTERN = re.compile(
    r"^"
    r"(?P<qty>"
    r"(?:\d+\s+\d+/\d+)"  # mixed fraction: 1 1/2
    r"|(?:\d+/\d+)"  # fraction: 1/2
    r"|(?:\d+\.?\d*)"  # decimal: 1, 1.5, 200
    r")?"
    r"\s*"
    r"(?P<unit>[a-zA-Z]+)?"
    r"\s+"
    r"(?:of\s+)?"
    r"(?P<ingredient>.+)"
    r"$"
)

_KNOWN_UNITS = (
    set(_CONVERSIONS["weight_to_g"].keys())
    | set(_CONVERSIONS["volume_to_ml"].keys())
    | _COUNTABLE
    | set(_UNIT_ALIASES.keys())
    | {"x", "large", "medium", "small"}
)


def _parse_quantity(text: str) -> float:
    """Parse a quantity string to a float, handling fractions."""
    text = text.strip()
    # Mixed fraction: "1 1/2"
    parts = text.split()
    if len(parts) == 2 and "/" in parts[1]:
        whole = float(parts[0])
        num, den = parts[1].split("/")
        return whole + float(num) / float(den)
    # Simple fraction: "1/2"
    if "/" in text:
        num, den = text.split("/")
        return float(num) / float(den)
    return float(text)


def parse_ingredient_line(text: str) -> RecipeIngredient:
    """Parse a free-text ingredient line into a RecipeIngredient.

    Examples:
        "2 large onions, diced" -> RecipeIngredient(onions, 2, whole, diced)
        "200g chicken breast" -> RecipeIngredient(chicken breast, 200, g)
        "1 tbsp olive oil" -> RecipeIngredient(olive oil, 1, tbsp)
        "salt and pepper" -> RecipeIngredient(salt and pepper, 1, whole)
    """
    text = text.strip()
    if not text:
        return RecipeIngredient(ingredient_name="", quantity=0, unit="whole")

    # Split off preparation instructions after comma
    preparation = ""
    if "," in text:
        main_part, preparation = text.split(",", 1)
        preparation = preparation.strip()
        text = main_part.strip()

    match = _QUANTITY_PATTERN.match(text)
    if not match:
        return RecipeIngredient(
            ingredient_name=text.lower(),
            quantity=1,
            unit="whole",
            preparation=preparation,
        )

    qty_str = match.group("qty")
    unit_str = match.group("unit") or ""
    ingredient = match.group("ingredient") or text

    quantity = _parse_quantity(qty_str) if qty_str else 1.0

    # Determine if the captured "unit" is actually a unit or part of the ingredient name
    unit_lower = unit_str.lower() if unit_str else ""
    if unit_lower in _KNOWN_UNITS:
        unit = canonicalize_unit(unit_lower)
        # "large", "medium", "small" are size descriptors, not real units
        if unit_lower in ("large", "medium", "small", "x"):
            ingredient = f"{unit_str} {ingredient}"
            unit = "whole"
    elif unit_str:
        # Not a known unit — it's part of the ingredient name
        ingredient = f"{unit_str} {ingredient}" if ingredient else unit_str
        unit = "whole"
    else:
        unit = "whole"

    return RecipeIngredient(
        ingredient_name=ingredient.strip().lower(),
        quantity=quantity,
        unit=unit,
        preparation=preparation,
    )


# --- Aggregation ---


@dataclass
class AggregatedIngredient:
    """An ingredient with total quantity aggregated across recipes."""
    ingredient_name: str
    quantity: float
    unit: str
    from_recipes: list[str]




def aggregate_ingredients(
    recipe_ingredients: list[RecipeIngredient],
    servings_multiplier: float = 1.0,
) -> list[AggregatedIngredient]:
    """Aggregate a list of recipe ingredients, combining duplicates.

    Converts compatible units to a common base before summing.
    Applies the servings_multiplier to all quantities.
    """
    # Group by normalised ingredient name
    groups: dict[str, list[RecipeIngredient]] = {}
    for ri in recipe_ingredients:
        key = ri.ingredient_name.strip().lower()
        groups.setdefault(key, []).append(ri)

    result: list[AggregatedIngredient] = []
    for name, items in groups.items():
        # Convert all to common units and sum
        total_g: float = 0
        total_ml: float = 0
        total_count: float = 0
        recipes: list[str] = []
        primary_unit = canonicalize_unit(items[0].unit)

        for item in items:
            qty = item.quantity * servings_multiplier
            canon = canonicalize_unit(item.unit)

            grams = normalize_to_grams(qty, canon)
            if grams is not None:
                total_g += grams
                if item.recipe_name and item.recipe_name not in recipes:
                    recipes.append(item.recipe_name)
                continue

            ml = normalize_to_ml(qty, canon)
            if ml is not None:
                total_ml += ml
                if item.recipe_name and item.recipe_name not in recipes:
                    recipes.append(item.recipe_name)
                continue

            # Countable / unknown unit
            total_count += qty
            if item.recipe_name and item.recipe_name not in recipes:
                recipes.append(item.recipe_name)

        # Build result entries (one per dimension that has values)
        if total_g > 0:
            q, u = (total_g / 1000, "kg") if total_g >= 1000 else (total_g, "g")
            result.append(AggregatedIngredient(name, round(q, 1), u, recipes))
        if total_ml > 0:
            q, u = (total_ml / 1000, "l") if total_ml >= 1000 else (total_ml, "ml")
            result.append(AggregatedIngredient(name, round(q, 1), u, recipes))
        if total_count > 0:
            result.append(AggregatedIngredient(
                name, round(total_count, 1), primary_unit, list(recipes)
            ))

    return sorted(result, key=lambda x: x.ingredient_name)
