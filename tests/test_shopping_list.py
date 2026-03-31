"""Tests for shopping list formatting and regular items."""

from datetime import date, timedelta

from shopping.models import (
    Frequency,
    IngredientCategory,
    RegularItem,
    ShoppingListItem,
)
from shopping.shopping_list import (
    check_regular_items,
    estimate_budget,
    format_shopping_list,
    regular_items_to_shopping_list,
)


class TestCheckRegularItems:
    def test_weekly_item_due(self):
        items = [
            RegularItem(
                name="Frozen Berries",
                frequency=Frequency.WEEKLY,
                last_ordered=date(2026, 3, 20),
                auto_add=True,
            )
        ]
        due = check_regular_items(items, today=date(2026, 3, 28))
        assert len(due) == 1
        assert due[0].name == "Frozen Berries"

    def test_weekly_item_not_due(self):
        items = [
            RegularItem(
                name="Frozen Berries",
                frequency=Frequency.WEEKLY,
                last_ordered=date(2026, 3, 25),
                auto_add=True,
            )
        ]
        due = check_regular_items(items, today=date(2026, 3, 28))
        assert len(due) == 0

    def test_never_ordered_item_is_due(self):
        items = [
            RegularItem(name="Milk", frequency=Frequency.WEEKLY, auto_add=True)
        ]
        due = check_regular_items(items, today=date(2026, 3, 28))
        assert len(due) == 1

    def test_auto_add_false_excluded(self):
        items = [
            RegularItem(
                name="Special Treat",
                frequency=Frequency.WEEKLY,
                last_ordered=None,
                auto_add=False,
            )
        ]
        due = check_regular_items(items, today=date(2026, 3, 28))
        assert len(due) == 0

    def test_next_due_date_used(self):
        items = [
            RegularItem(
                name="Laundry Detergent",
                frequency=Frequency.MONTHLY,
                next_due=date(2026, 3, 27),
                auto_add=True,
            )
        ]
        due = check_regular_items(items, today=date(2026, 3, 28))
        assert len(due) == 1

    def test_fortnightly_item(self):
        items = [
            RegularItem(
                name="Eggs",
                frequency=Frequency.FORTNIGHTLY,
                last_ordered=date(2026, 3, 10),
                auto_add=True,
            )
        ]
        due = check_regular_items(items, today=date(2026, 3, 28))
        assert len(due) == 1


class TestRegularItemsToShoppingList:
    def test_converts_correctly(self):
        items = [
            RegularItem(name="Frozen Berries", typical_quantity=1, unit="bag"),
            RegularItem(name="Milk", typical_quantity=2, unit="l"),
        ]
        result = regular_items_to_shopping_list(items)
        assert len(result) == 2
        assert result[0].ingredient_name == "Frozen Berries"
        assert result[0].is_regular_item
        assert result[1].quantity_needed == 2
        assert result[1].unit == "l"


class TestFormatShoppingList:
    def test_empty_list(self):
        assert format_shopping_list([]) == "Shopping list is empty!"

    def test_flat_list(self):
        items = [
            ShoppingListItem("chicken breast", 600, "g", from_recipes=["Stir Fry"]),
            ShoppingListItem("rice", 400, "g", from_recipes=["Stir Fry", "Curry"]),
        ]
        result = format_shopping_list(items, group_by_category=False)
        assert "600 g chicken breast" in result
        assert "400 g rice" in result
        assert "Stir Fry" in result

    def test_regular_item_marked(self):
        items = [
            ShoppingListItem("frozen berries", 1, "bag", is_regular_item=True),
        ]
        result = format_shopping_list(items, group_by_category=False)
        assert "[regular]" in result

    def test_brand_shown(self):
        items = [
            ShoppingListItem(
                "pasta", 500, "g",
                preferred_brand="De Cecco",
            ),
        ]
        result = format_shopping_list(items, group_by_category=False)
        assert "De Cecco" in result


class TestEstimateBudget:
    def test_estimate_format(self):
        items = [
            ShoppingListItem("item1", 1, "whole"),
            ShoppingListItem("item2", 1, "whole"),
            ShoppingListItem("item3", 1, "whole"),
        ]
        result = estimate_budget(items)
        assert "3 items" in result
        assert "£" in result
