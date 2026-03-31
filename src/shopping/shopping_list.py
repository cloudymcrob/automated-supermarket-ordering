"""Shopping list formatting and regular items checking."""

from __future__ import annotations

from datetime import date, timedelta

from shopping.models import (
    Frequency,
    IngredientCategory,
    RegularItem,
    ShoppingListItem,
)


# Frequency to approximate days between orders
_FREQUENCY_DAYS: dict[Frequency, int] = {
    Frequency.WEEKLY: 7,
    Frequency.FORTNIGHTLY: 14,
    Frequency.MONTHLY: 30,
    Frequency.AS_NEEDED: 999,  # Only added manually
}


def check_regular_items(
    regular_items: list[RegularItem],
    today: date | None = None,
) -> list[RegularItem]:
    """Check which regular items are due for reorder.

    An item is due if:
    - auto_add is True AND
    - next_due is today or earlier, OR last_ordered is None, OR
      days since last_ordered >= frequency interval
    """
    today = today or date.today()
    due: list[RegularItem] = []

    for item in regular_items:
        if not item.auto_add:
            continue

        if item.next_due and item.next_due <= today:
            due.append(item)
        elif item.last_ordered is None:
            due.append(item)
        else:
            interval = _FREQUENCY_DAYS.get(item.frequency, 7)
            if (today - item.last_ordered).days >= interval:
                due.append(item)

    return due


def regular_items_to_shopping_list(
    items: list[RegularItem],
) -> list[ShoppingListItem]:
    """Convert due regular items to shopping list items."""
    return [
        ShoppingListItem(
            ingredient_name=item.name,
            quantity_needed=item.typical_quantity,
            unit=item.unit,
            is_regular_item=True,
        )
        for item in items
    ]


def format_shopping_list(
    items: list[ShoppingListItem],
    group_by_category: bool = True,
) -> str:
    """Format a shopping list for display, optionally grouped by category.

    Output is human-readable markdown suitable for Slack messages.
    """
    if not items:
        return "Shopping list is empty!"

    if not group_by_category:
        return _format_items(items)

    # Group items by category
    groups: dict[str, list[ShoppingListItem]] = {}
    for item in items:
        cat = item.category.value if item.category else "Other"
        groups.setdefault(cat, []).append(item)

    lines: list[str] = []
    for category in sorted(groups.keys()):
        cat_items = groups[category]
        lines.append(f"**{category}**")
        lines.append(_format_items(cat_items))
        lines.append("")

    return "\n".join(lines).strip()


def _format_items(items: list[ShoppingListItem]) -> str:
    """Format a flat list of shopping items."""
    lines: list[str] = []
    for item in sorted(items, key=lambda x: x.ingredient_name):
        qty = item.quantity_needed
        qty_str = str(int(qty)) if qty == int(qty) else f"{qty:.1f}"

        unit_str = f" {item.unit}" if item.unit and item.unit != "whole" else ""
        brand_str = f" ({item.preferred_brand})" if item.preferred_brand else ""
        recipe_str = ""
        if item.from_recipes:
            recipe_str = f" — for {', '.join(item.from_recipes)}"
        regular_str = " [regular]" if item.is_regular_item else ""

        lines.append(
            f"- {qty_str}{unit_str} {item.ingredient_name}"
            f"{brand_str}{regular_str}{recipe_str}"
        )
    return "\n".join(lines)


def estimate_budget(items: list[ShoppingListItem]) -> str:
    """Provide a rough budget estimate based on item count.

    This is a very rough heuristic — actual prices come from Tesco during ordering.
    Assumes ~£2-3 per item on average for value products.
    """
    num_items = len(items)
    low = num_items * 1.5
    high = num_items * 3.0
    return f"Rough estimate: £{low:.0f}-£{high:.0f} ({num_items} items)"
