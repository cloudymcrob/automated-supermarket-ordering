"""Integration tests for the meal planning pipeline.

These tests use real Recipe objects (simulating what we'd get from Notion)
to verify the full scoring → selection pipeline works end-to-end.
"""

import json
from datetime import date, timedelta

from shopping.meal_planning import score_recipes, select_weekly_meals
from shopping.models import CookStyle, MealType, Recipe


def _make_recipes() -> list[Recipe]:
    """Build a realistic set of recipes matching what's in Notion."""
    return [
        Recipe(name="Bolognese", cuisine="Italian", meal_types=[MealType.DINNER],
               times_cooked=0, active=True),
        Recipe(name="Chicken lemony couscous", cuisine="Mediterranean",
               meal_types=[MealType.DINNER], times_cooked=0, active=True),
        Recipe(name="Gong bao chicken", cuisine="Chinese",
               meal_types=[MealType.DINNER], times_cooked=0, active=True),
        Recipe(name="Dal tadka", cuisine="Indian",
               meal_types=[MealType.DINNER], times_cooked=0, active=True),
        Recipe(name="Pad see ew", cuisine="Thai",
               meal_types=[MealType.DINNER], times_cooked=0, active=True),
        Recipe(name="Sausage bean casserole", cuisine="British",
               meal_types=[MealType.DINNER], times_cooked=0, active=True),
        Recipe(name="Chicken adobo", cuisine="Other",
               meal_types=[MealType.DINNER], times_cooked=0, active=True),
        Recipe(name="Baked ratatouille & goat's cheese", cuisine="Mediterranean",
               meal_types=[MealType.DINNER], times_cooked=0, active=True),
        Recipe(name="Miso salmon traybake", cuisine="Japanese",
               meal_types=[MealType.DINNER], times_cooked=0, active=True),
        Recipe(name="Chilli con carne", cuisine="Mexican",
               meal_types=[MealType.DINNER], times_cooked=0, active=True),
        # Lunch-eligible recipes
        Recipe(name="Egg fried rice", cuisine="Chinese",
               meal_types=[MealType.LUNCH, MealType.DINNER],
               times_cooked=0, prep_time_mins=5, cook_time_mins=10, active=True),
        Recipe(name="Stir fry noodles", cuisine="Chinese",
               meal_types=[MealType.DINNER, MealType.LUNCH],
               times_cooked=0, prep_time_mins=10, cook_time_mins=10, active=True),
        Recipe(name="Chicken stir fry with rice", cuisine="Chinese",
               meal_types=[MealType.LUNCH, MealType.DINNER],
               times_cooked=0, prep_time_mins=5, cook_time_mins=15, active=True),
        Recipe(name="Poke bowl with teriyaki chicken", cuisine="Japanese",
               meal_types=[MealType.LUNCH, MealType.DINNER],
               times_cooked=0, prep_time_mins=15, cook_time_mins=10, active=True),
        Recipe(name="Spanish omelette with chorizo", cuisine="Mediterranean",
               meal_types=[MealType.DINNER, MealType.LUNCH],
               times_cooked=0, prep_time_mins=10, cook_time_mins=15, active=True),
        Recipe(name="Vietnamese banh mi tofu sandwich", cuisine="Other",
               meal_types=[MealType.LUNCH],
               times_cooked=0, prep_time_mins=10, cook_time_mins=5, active=True),
    ]


class TestScoreRecipesIntegration:
    """Test scoring with realistic recipe data."""

    def test_all_new_recipes_get_never_cooked_bonus(self):
        recipes = _make_recipes()
        scored = score_recipes(recipes)
        for sr in scored:
            assert any("Never cooked" in r for r in sr.reasons)

    def test_recently_cooked_penalized(self):
        recipes = _make_recipes()
        scored_fresh = score_recipes(recipes, recent_recipe_names=["Bolognese"])
        bolognese = next(sr for sr in scored_fresh if sr.recipe.name == "Bolognese")
        others = [sr for sr in scored_fresh if sr.recipe.name != "Bolognese"]
        # Bolognese should score lower than all uncooked recipes
        assert all(bolognese.score < other.score for other in others)

    def test_allergens_excluded(self):
        from shopping.models import RecipeIngredient
        recipes = _make_recipes()
        # Add a recipe with nuts
        nut_recipe = Recipe(
            name="Satay chicken", cuisine="Thai",
            meal_types=[MealType.DINNER], active=True,
            ingredients=[RecipeIngredient("peanut butter", 2, "tbsp")]
        )
        recipes.append(nut_recipe)
        scored = score_recipes(recipes)
        scored_names = {sr.recipe.name for sr in scored}
        assert "Satay chicken" not in scored_names

    def test_inactive_excluded(self):
        recipes = _make_recipes()
        recipes.append(Recipe(name="Inactive dish", active=False))
        scored = score_recipes(recipes)
        assert all(sr.recipe.name != "Inactive dish" for sr in scored)


class TestSelectWeeklyMealsIntegration:
    """Test the full selection pipeline."""

    def test_selects_5_dinners_5_lunches(self):
        recipes = _make_recipes()
        scored = score_recipes(recipes)
        selection = select_weekly_meals(scored, num_dinners=5, num_lunches=5)
        assert len(selection["dinners"]) == 5
        assert len(selection["lunches"]) == 5

    def test_cuisine_diversity_in_dinners(self):
        recipes = _make_recipes()
        scored = score_recipes(recipes)
        selection = select_weekly_meals(scored, num_dinners=5, num_lunches=5)
        dinner_cuisines = [sr.recipe.cuisine for sr in selection["dinners"]]
        # With 10 dinner-eligible recipes across 7 cuisines, should have variety
        assert len(set(dinner_cuisines)) >= 4, f"Only {len(set(dinner_cuisines))} unique cuisines: {dinner_cuisines}"

    def test_no_duplicate_recipes(self):
        recipes = _make_recipes()
        scored = score_recipes(recipes)
        selection = select_weekly_meals(scored, num_dinners=5, num_lunches=5)
        all_names = [sr.recipe.name for sr in selection["dinners"] + selection["lunches"]]
        assert len(all_names) == len(set(all_names)), f"Duplicates found: {all_names}"

    def test_dual_type_recipes_fill_both_slots(self):
        """Recipes with both Lunch and Dinner types should be usable for either."""
        recipes = _make_recipes()
        scored = score_recipes(recipes)
        selection = select_weekly_meals(scored, num_dinners=5, num_lunches=5)
        all_selected = selection["dinners"] + selection["lunches"]
        selected_names = {sr.recipe.name for sr in all_selected}
        # At least some dual-type recipes should appear
        dual_type_recipes = {"Egg fried rice", "Stir fry noodles",
                            "Chicken stir fry with rice", "Poke bowl with teriyaki chicken",
                            "Spanish omelette with chorizo"}
        assert selected_names & dual_type_recipes, "No dual-type recipes were selected"


class TestNotionRecipeConversion:
    """Test converting Notion query results to Recipe objects."""

    def test_parse_notion_row(self):
        """Simulate parsing a Notion query result row into a Recipe."""
        row = {
            "Name": "Bolognese",
            "Cuisine": "Italian",
            "Meal Type": '[\"Dinner\"]',
            "Active": "__YES__",
            "Servings": 2,
            "Tags": '[\"Batch Cook\", \"Freezable\", \"Comfort\"]',
            "Source URL": None,
            "Times Cooked": None,
            "Rating": None,
            "Notes": None,
        }

        # Parse meal types from JSON array
        meal_type_map = {"Lunch": MealType.LUNCH, "Dinner": MealType.DINNER}
        raw_meal_types = json.loads(row["Meal Type"]) if row["Meal Type"] else ["Dinner"]
        meal_types = [meal_type_map[mt] for mt in raw_meal_types]

        recipe = Recipe(
            name=row["Name"],
            cuisine=row["Cuisine"] or "",
            meal_types=meal_types,
            active=row["Active"] == "__YES__",
            servings=int(row["Servings"] or 2),
            times_cooked=int(row["Times Cooked"] or 0),
            rating=int(row["Rating"]) if row["Rating"] else None,
            tags=json.loads(row["Tags"]) if row["Tags"] else [],
        )

        assert recipe.name == "Bolognese"
        assert recipe.cuisine == "Italian"
        assert recipe.meal_types == [MealType.DINNER]
        assert recipe.active is True
        assert recipe.tags == ["Batch Cook", "Freezable", "Comfort"]
        assert recipe.times_cooked == 0

    def test_parse_dual_meal_type(self):
        row_meal_type = '[\"Lunch\", \"Dinner\"]'
        meal_type_map = {"Lunch": MealType.LUNCH, "Dinner": MealType.DINNER}
        meal_types = [meal_type_map[mt] for mt in json.loads(row_meal_type)]
        assert MealType.LUNCH in meal_types
        assert MealType.DINNER in meal_types


class TestRecipePortionModel:
    """Test the quantity_multiplier / num_portions_per_quantity model."""

    def test_effective_portions_default(self):
        """Default: servings / 1.5."""
        r = Recipe(name="Test", servings=4)
        assert abs(r.effective_portions_per_quantity - 4 / 1.5) < 0.01

    def test_effective_portions_with_feedback(self):
        """Uses num_portions_per_quantity when set."""
        r = Recipe(name="Test", servings=4, num_portions_per_quantity=5.0)
        assert r.effective_portions_per_quantity == 5.0

    def test_total_portions_default(self):
        """At quantity_multiplier=1, total_portions = effective_portions."""
        r = Recipe(name="Test", servings=4)
        assert abs(r.total_portions - 4 / 1.5) < 0.01

    def test_total_portions_with_multiplier(self):
        """quantity_multiplier scales total_portions."""
        r = Recipe(name="Test", servings=4, quantity_multiplier=3.0)
        expected = (4 / 1.5) * 3.0
        assert abs(r.total_portions - expected) < 0.01

    def test_total_portions_with_feedback_and_multiplier(self):
        r = Recipe(name="Test", servings=4, num_portions_per_quantity=5.0,
                   quantity_multiplier=2.0)
        assert r.total_portions == 10.0

    def test_meals_covered_quick(self):
        """Quick recipe at default multiplier covers 1 meal."""
        r = Recipe(name="Stir Fry", servings=4, quantity_multiplier=1.0)
        # 4/1.5 = 2.67 portions, /2 people = 1.33, rounds to 1
        assert r.meals_covered == 1

    def test_meals_covered_batch(self):
        """Batch recipe with multiplier=3 covers multiple meals."""
        r = Recipe(name="Chili", servings=4, quantity_multiplier=3.0)
        # (4/1.5)*3 = 8 portions, /2 = 4 meals
        assert r.meals_covered == 4

    def test_cook_style_default(self):
        r = Recipe(name="Test")
        assert r.cook_style == CookStyle.QUICK
