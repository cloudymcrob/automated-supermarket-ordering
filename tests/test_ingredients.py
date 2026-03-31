"""Tests for ingredient parsing, unit conversion, and aggregation."""

import pytest

from shopping.ingredients import (
    AggregatedIngredient,
    aggregate_ingredients,
    canonicalize_unit,
    convert_to_common_unit,
    format_quantity,
    normalize_to_grams,
    normalize_to_ml,
    parse_ingredient_line,
    units_compatible,
)
from shopping.models import RecipeIngredient


class TestCanonicalizeUnit:
    def test_standard_units_unchanged(self):
        assert canonicalize_unit("g") == "g"
        assert canonicalize_unit("ml") == "ml"
        assert canonicalize_unit("tsp") == "tsp"

    def test_plural_to_singular(self):
        assert canonicalize_unit("grams") == "g"
        assert canonicalize_unit("cloves") == "clove"
        assert canonicalize_unit("cans") == "can"

    def test_verbose_to_short(self):
        assert canonicalize_unit("tablespoon") == "tbsp"
        assert canonicalize_unit("teaspoon") == "tsp"
        assert canonicalize_unit("kilogram") == "kg"
        assert canonicalize_unit("litre") == "l"

    def test_case_insensitive(self):
        assert canonicalize_unit("GRAMS") == "g"
        assert canonicalize_unit("Tbsp") == "tbsp"


class TestNormalize:
    def test_grams_identity(self):
        assert normalize_to_grams(100, "g") == 100

    def test_kg_to_grams(self):
        assert normalize_to_grams(1.5, "kg") == 1500

    def test_oz_to_grams(self):
        assert normalize_to_grams(1, "oz") == pytest.approx(28.35)

    def test_non_weight_returns_none(self):
        assert normalize_to_grams(100, "ml") is None
        assert normalize_to_grams(1, "whole") is None

    def test_ml_identity(self):
        assert normalize_to_ml(100, "ml") == 100

    def test_litre_to_ml(self):
        assert normalize_to_ml(2, "l") == 2000

    def test_tsp_to_ml(self):
        assert normalize_to_ml(1, "tsp") == 5

    def test_tbsp_to_ml(self):
        assert normalize_to_ml(1, "tbsp") == 15

    def test_non_volume_returns_none(self):
        assert normalize_to_ml(100, "g") is None


class TestUnitsCompatible:
    def test_same_unit(self):
        assert units_compatible("g", "g")
        assert units_compatible("whole", "whole")

    def test_weight_units_compatible(self):
        assert units_compatible("g", "kg")
        assert units_compatible("oz", "g")

    def test_volume_units_compatible(self):
        assert units_compatible("ml", "l")
        assert units_compatible("tsp", "ml")

    def test_weight_volume_incompatible(self):
        assert not units_compatible("g", "ml")

    def test_countable_incompatible_with_weight(self):
        assert not units_compatible("whole", "g")


class TestConvertToCommonUnit:
    def test_grams_stay_grams(self):
        assert convert_to_common_unit(500, "g") == (500, "g")

    def test_kg_stays_kg(self):
        assert convert_to_common_unit(1500, "g") == (1.5, "kg")

    def test_kg_converts_to_g(self):
        assert convert_to_common_unit(0.5, "kg") == (500, "g")

    def test_ml_stays_ml(self):
        assert convert_to_common_unit(250, "ml") == (250, "ml")

    def test_large_ml_becomes_l(self):
        assert convert_to_common_unit(1500, "ml") == (1.5, "l")

    def test_countable_unchanged(self):
        assert convert_to_common_unit(3, "whole") == (3, "whole")
        assert convert_to_common_unit(2, "can") == (2, "can")


class TestParseIngredientLine:
    def test_weight_ingredient(self):
        result = parse_ingredient_line("200g chicken breast")
        assert result.quantity == 200
        assert result.unit == "g"
        assert result.ingredient_name == "chicken breast"

    def test_volume_ingredient(self):
        result = parse_ingredient_line("1 tbsp olive oil")
        assert result.quantity == 1
        assert result.unit == "tbsp"
        assert result.ingredient_name == "olive oil"

    def test_countable_ingredient(self):
        result = parse_ingredient_line("2 onions")
        assert result.quantity == 2
        assert result.ingredient_name == "onions"

    def test_large_size_descriptor(self):
        result = parse_ingredient_line("2 large onions")
        assert result.quantity == 2
        assert result.unit == "whole"
        assert "large" in result.ingredient_name
        assert "onions" in result.ingredient_name

    def test_preparation_after_comma(self):
        result = parse_ingredient_line("2 large onions, diced")
        assert result.preparation == "diced"
        assert result.quantity == 2

    def test_fraction(self):
        result = parse_ingredient_line("1/2 tsp salt")
        assert result.quantity == 0.5
        assert result.unit == "tsp"
        assert result.ingredient_name == "salt"

    def test_mixed_fraction(self):
        result = parse_ingredient_line("1 1/2 cups flour")
        assert result.quantity == 1.5
        assert result.unit == "cup"
        assert "flour" in result.ingredient_name

    def test_no_quantity(self):
        result = parse_ingredient_line("salt and pepper")
        assert result.quantity == 1
        assert result.unit == "whole"
        assert result.ingredient_name == "salt and pepper"

    def test_can_unit(self):
        result = parse_ingredient_line("1 can chopped tomatoes")
        assert result.quantity == 1
        assert result.unit == "can"
        assert result.ingredient_name == "chopped tomatoes"

    def test_kg_ingredient(self):
        result = parse_ingredient_line("1.5kg potatoes")
        assert result.quantity == 1.5
        assert result.unit == "kg"
        assert result.ingredient_name == "potatoes"

    def test_empty_string(self):
        result = parse_ingredient_line("")
        assert result.quantity == 0


class TestAggregateIngredients:
    def test_same_ingredient_same_unit(self):
        items = [
            RecipeIngredient("onion", 2, "whole", recipe_name="Curry"),
            RecipeIngredient("onion", 1, "whole", recipe_name="Stew"),
        ]
        result = aggregate_ingredients(items)
        assert len(result) == 1
        assert result[0].ingredient_name == "onion"
        assert result[0].quantity == 3
        assert set(result[0].from_recipes) == {"Curry", "Stew"}

    def test_same_ingredient_different_weight_units(self):
        items = [
            RecipeIngredient("flour", 200, "g", recipe_name="Cake"),
            RecipeIngredient("flour", 0.15, "kg", recipe_name="Bread"),
        ]
        result = aggregate_ingredients(items)
        assert len(result) == 1
        assert result[0].unit == "g"
        assert result[0].quantity == 350

    def test_servings_multiplier(self):
        items = [
            RecipeIngredient("chicken breast", 200, "g", recipe_name="Stir Fry"),
        ]
        result = aggregate_ingredients(items, servings_multiplier=1.5)
        assert result[0].quantity == 300

    def test_different_ingredients_kept_separate(self):
        items = [
            RecipeIngredient("onion", 2, "whole", recipe_name="Curry"),
            RecipeIngredient("garlic", 3, "clove", recipe_name="Curry"),
        ]
        result = aggregate_ingredients(items)
        assert len(result) == 2
        names = {r.ingredient_name for r in result}
        assert names == {"garlic", "onion"}

    def test_volume_aggregation(self):
        items = [
            RecipeIngredient("olive oil", 2, "tbsp", recipe_name="Pasta"),
            RecipeIngredient("olive oil", 1, "tbsp", recipe_name="Salad"),
        ]
        result = aggregate_ingredients(items)
        assert len(result) == 1
        assert result[0].quantity == 45  # 3 tbsp = 45ml
        assert result[0].unit == "ml"

    def test_results_sorted_alphabetically(self):
        items = [
            RecipeIngredient("zucchini", 1, "whole"),
            RecipeIngredient("apple", 2, "whole"),
            RecipeIngredient("banana", 1, "whole"),
        ]
        result = aggregate_ingredients(items)
        names = [r.ingredient_name for r in result]
        assert names == ["apple", "banana", "zucchini"]


class TestFormatQuantity:
    def test_whole_number(self):
        assert format_quantity(3.0, "whole") == "3"

    def test_decimal(self):
        assert format_quantity(1.5, "kg") == "1.5kg"

    def test_whole_unit(self):
        assert format_quantity(2.0, "whole") == "2"

    def test_g_unit(self):
        assert format_quantity(200, "g") == "200g"
