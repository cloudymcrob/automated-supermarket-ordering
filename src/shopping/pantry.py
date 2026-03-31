"""Pantry inventory deduction logic."""

from __future__ import annotations

from shopping.ingredients import (
    AggregatedIngredient,
    canonicalize_unit,
    normalize_to_grams,
    normalize_to_ml,
    units_compatible,
)
from shopping.models import (
    IngredientCategory,
    PantryItem,
    PriceSensitivity,
    ShoppingListItem,
)


def deduct_pantry(
    needed: list[AggregatedIngredient],
    pantry: list[PantryItem],
) -> list[ShoppingListItem]:
    """Subtract pantry stock from needed ingredients to produce a shopping list.

    Returns only items that still need to be purchased (quantity > 0 after deduction).
    """
    # Index pantry by normalised ingredient name
    pantry_index: dict[str, PantryItem] = {}
    for item in pantry:
        key = item.ingredient_name.strip().lower()
        pantry_index[key] = item

    shopping_list: list[ShoppingListItem] = []

    for agg in needed:
        key = agg.ingredient_name.strip().lower()
        pantry_item = pantry_index.get(key)

        if pantry_item is None:
            # Not in pantry — need to buy the full amount
            shopping_list.append(ShoppingListItem(
                ingredient_name=agg.ingredient_name,
                quantity_needed=agg.quantity,
                unit=agg.unit,
                from_recipes=list(agg.from_recipes),
            ))
            continue

        remaining = _compute_remaining(agg, pantry_item)
        if remaining > 0:
            shopping_list.append(ShoppingListItem(
                ingredient_name=agg.ingredient_name,
                quantity_needed=round(remaining, 1),
                unit=agg.unit,
                from_recipes=list(agg.from_recipes),
            ))

    return shopping_list


def _compute_remaining(
    needed: AggregatedIngredient,
    pantry_item: PantryItem,
) -> float:
    """Compute how much still needs to be bought after pantry deduction."""
    needed_unit = canonicalize_unit(needed.unit)
    pantry_unit = canonicalize_unit(pantry_item.unit)

    # Same unit — simple subtraction
    if needed_unit == pantry_unit:
        return needed.quantity - pantry_item.quantity

    # Both weight units — convert to grams
    needed_g = normalize_to_grams(needed.quantity, needed_unit)
    pantry_g = normalize_to_grams(pantry_item.quantity, pantry_unit)
    if needed_g is not None and pantry_g is not None:
        remaining_g = needed_g - pantry_g
        if remaining_g <= 0:
            return 0
        # Return in the same unit as needed
        factor = needed.quantity / needed_g if needed_g > 0 else 1
        return remaining_g * factor

    # Both volume units — convert to ml
    needed_ml = normalize_to_ml(needed.quantity, needed_unit)
    pantry_ml = normalize_to_ml(pantry_item.quantity, pantry_unit)
    if needed_ml is not None and pantry_ml is not None:
        remaining_ml = needed_ml - pantry_ml
        if remaining_ml <= 0:
            return 0
        factor = needed.quantity / needed_ml if needed_ml > 0 else 1
        return remaining_ml * factor

    # Incompatible units — assume we need the full amount (conservative)
    return needed.quantity


def update_pantry_after_cooking(
    pantry: list[PantryItem],
    used: list[AggregatedIngredient],
) -> list[PantryItem]:
    """Return updated pantry quantities after cooking a meal.

    Deducts used quantities from pantry items. Items that reach zero
    or below are set to quantity=0 with status OUT.
    """
    from shopping.models import PantryStatus

    pantry_index: dict[str, PantryItem] = {}
    for item in pantry:
        key = item.ingredient_name.strip().lower()
        pantry_index[key] = item

    updated: list[PantryItem] = list(pantry)

    for agg in used:
        key = agg.ingredient_name.strip().lower()
        pantry_item = pantry_index.get(key)
        if pantry_item is None:
            continue

        deducted = _deduct_quantity(pantry_item, agg)
        pantry_item.quantity = max(0, deducted)
        if pantry_item.quantity == 0:
            pantry_item.status = PantryStatus.OUT
        elif pantry_item.quantity < agg.quantity * 0.25:
            pantry_item.status = PantryStatus.LOW

    return updated


def _deduct_quantity(pantry_item: PantryItem, used: AggregatedIngredient) -> float:
    """Deduct used quantity from pantry item, handling unit conversion."""
    pantry_unit = canonicalize_unit(pantry_item.unit)
    used_unit = canonicalize_unit(used.unit)

    if pantry_unit == used_unit:
        return pantry_item.quantity - used.quantity

    # Weight conversion
    pantry_g = normalize_to_grams(pantry_item.quantity, pantry_unit)
    used_g = normalize_to_grams(used.quantity, used_unit)
    if pantry_g is not None and used_g is not None:
        remaining_g = pantry_g - used_g
        factor = pantry_item.quantity / pantry_g if pantry_g > 0 else 1
        return remaining_g * factor

    # Volume conversion
    pantry_ml = normalize_to_ml(pantry_item.quantity, pantry_unit)
    used_ml = normalize_to_ml(used.quantity, used_unit)
    if pantry_ml is not None and used_ml is not None:
        remaining_ml = pantry_ml - used_ml
        factor = pantry_item.quantity / pantry_ml if pantry_ml > 0 else 1
        return remaining_ml * factor

    # Incompatible — leave pantry unchanged (conservative)
    return pantry_item.quantity
