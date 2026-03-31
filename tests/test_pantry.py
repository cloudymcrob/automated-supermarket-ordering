"""Tests for pantry deduction logic."""

from datetime import date

import pytest

from shopping.ingredients import AggregatedIngredient
from shopping.models import PantryItem, PantryStatus
from shopping.pantry import deduct_pantry, update_pantry_after_cooking


class TestDeductPantry:
    def test_item_not_in_pantry(self):
        needed = [AggregatedIngredient("chicken breast", 300, "g", ["Stir Fry"])]
        pantry: list[PantryItem] = []
        result = deduct_pantry(needed, pantry)
        assert len(result) == 1
        assert result[0].ingredient_name == "chicken breast"
        assert result[0].quantity_needed == 300

    def test_item_fully_in_pantry(self):
        needed = [AggregatedIngredient("rice", 200, "g", ["Curry"])]
        pantry = [PantryItem("rice", 500, "g")]
        result = deduct_pantry(needed, pantry)
        assert len(result) == 0  # Nothing to buy

    def test_item_partially_in_pantry(self):
        needed = [AggregatedIngredient("flour", 350, "g", ["Cake"])]
        pantry = [PantryItem("flour", 200, "g")]
        result = deduct_pantry(needed, pantry)
        assert len(result) == 1
        assert result[0].quantity_needed == 150

    def test_cross_unit_deduction_weight(self):
        needed = [AggregatedIngredient("potatoes", 1.5, "kg", ["Mash"])]
        pantry = [PantryItem("potatoes", 500, "g")]
        result = deduct_pantry(needed, pantry)
        assert len(result) == 1
        assert result[0].quantity_needed == pytest.approx(1.0, abs=0.1)

    def test_multiple_items(self):
        needed = [
            AggregatedIngredient("onion", 3, "whole", ["Curry", "Stew"]),
            AggregatedIngredient("garlic", 4, "clove", ["Curry"]),
            AggregatedIngredient("rice", 400, "g", ["Curry"]),
        ]
        pantry = [
            PantryItem("onion", 1, "whole"),
            PantryItem("rice", 400, "g"),
        ]
        result = deduct_pantry(needed, pantry)
        assert len(result) == 2  # onion (partial) + garlic (missing)
        names = {r.ingredient_name for r in result}
        assert names == {"onion", "garlic"}

    def test_case_insensitive_matching(self):
        needed = [AggregatedIngredient("Chicken Breast", 300, "g", ["Stir Fry"])]
        pantry = [PantryItem("chicken breast", 300, "g")]
        result = deduct_pantry(needed, pantry)
        assert len(result) == 0


class TestUpdatePantryAfterCooking:
    def test_deducts_used_quantities(self):
        pantry = [
            PantryItem("rice", 500, "g"),
            PantryItem("onion", 4, "whole"),
        ]
        used = [
            AggregatedIngredient("rice", 200, "g", ["Curry"]),
            AggregatedIngredient("onion", 2, "whole", ["Curry"]),
        ]
        result = update_pantry_after_cooking(pantry, used)
        rice = next(p for p in result if p.ingredient_name == "rice")
        onion = next(p for p in result if p.ingredient_name == "onion")
        assert rice.quantity == 300
        assert onion.quantity == 2

    def test_sets_out_status_at_zero(self):
        pantry = [PantryItem("butter", 50, "g")]
        used = [AggregatedIngredient("butter", 50, "g", ["Toast"])]
        result = update_pantry_after_cooking(pantry, used)
        assert result[0].quantity == 0
        assert result[0].status == PantryStatus.OUT

    def test_sets_low_status(self):
        pantry = [PantryItem("olive oil", 100, "ml")]
        used = [AggregatedIngredient("olive oil", 90, "ml", ["Pasta"])]
        result = update_pantry_after_cooking(pantry, used)
        assert result[0].quantity == 10
        assert result[0].status == PantryStatus.LOW

    def test_unused_items_unchanged(self):
        pantry = [
            PantryItem("salt", 500, "g"),
            PantryItem("rice", 300, "g"),
        ]
        used = [AggregatedIngredient("rice", 200, "g", ["Curry"])]
        result = update_pantry_after_cooking(pantry, used)
        salt = next(p for p in result if p.ingredient_name == "salt")
        assert salt.quantity == 500
        assert salt.status == PantryStatus.IN_STOCK
