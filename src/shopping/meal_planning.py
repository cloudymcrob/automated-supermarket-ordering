"""Recipe selection and scoring for weekly meal planning."""

from __future__ import annotations

from datetime import date

from shopping.models import (
    MealType,
    Recipe,
    ScoredRecipe,
)


def score_recipes(
    recipes: list[Recipe],
    recent_recipe_names: list[str] | None = None,
    today: date | None = None,
) -> list[ScoredRecipe]:
    """Score and rank recipes for meal planning.

    Scoring is primarily recency-based — surface dishes not cooked recently.
    The calling agent handles fridge/pantry awareness and creative selection
    (cuisine variety, protein mix, cook style balance).

    Recipes containing allergens are excluded entirely.
    """
    today = today or date.today()
    recent = set(r.lower() for r in (recent_recipe_names or []))

    scored: list[ScoredRecipe] = []

    for recipe in recipes:
        if not recipe.active:
            continue
        if recipe.contains_allergen():
            continue

        score = 0.0
        reasons: list[str] = []

        # --- Recency (primary factor, 0-50 points) ---
        if recipe.name.lower() in recent:
            score -= 30
            reasons.append("Cooked in last 2-3 weeks (-30)")
        elif recipe.last_cooked:
            days_since = (today - recipe.last_cooked).days
            recency_bonus = min(50, days_since / 2)
            score += recency_bonus
            reasons.append(f"Not cooked for {days_since} days (+{recency_bonus:.0f})")
        else:
            score += 40
            reasons.append("Never cooked before (+40)")

        # --- Rating (0-15 points) ---
        if recipe.rating:
            rating_score = recipe.rating * 3
            score += rating_score
            reasons.append(f"Rating {recipe.rating}/5 (+{rating_score})")

        # --- Variety bonus for rarely cooked (0-10 points) ---
        if recipe.times_cooked <= 2:
            variety_bonus = 10 - (recipe.times_cooked * 3)
            if variety_bonus > 0:
                score += variety_bonus
                reasons.append(f"Cooked only {recipe.times_cooked}x (+{variety_bonus})")

        scored.append(ScoredRecipe(recipe=recipe, score=score, reasons=reasons))

    return sorted(scored, key=lambda s: s.score, reverse=True)


def select_weekly_meals(
    scored_recipes: list[ScoredRecipe],
    num_dinners: int = 5,
    num_lunches: int = 5,
) -> dict[str, list[ScoredRecipe]]:
    """Select a balanced set of meals for the week from scored recipes.

    Returns {"dinners": [...], "lunches": [...]} with diverse cuisines.

    Strategy:
    1. First fill dinner-only recipes into dinner slots (with cuisine diversity)
    2. Then fill lunch-only recipes into lunch slots
    3. Finally assign dual-type recipes to whichever slot still needs filling
    """
    dinners: list[ScoredRecipe] = []
    lunches: list[ScoredRecipe] = []
    used_cuisines: set[str] = set()
    selected_names: set[str] = set()

    # Categorise recipes
    dinner_only: list[ScoredRecipe] = []
    lunch_only: list[ScoredRecipe] = []
    dual_type: list[ScoredRecipe] = []

    for sr in scored_recipes:
        is_lunch = MealType.LUNCH in sr.recipe.meal_types
        is_dinner = MealType.DINNER in sr.recipe.meal_types
        if is_lunch and is_dinner:
            dual_type.append(sr)
        elif is_dinner:
            dinner_only.append(sr)
        elif is_lunch:
            lunch_only.append(sr)

    # Pass 1: Fill dinners from dinner-only (with cuisine diversity)
    for sr in dinner_only:
        if len(dinners) >= num_dinners:
            break
        if sr.recipe.cuisine and sr.recipe.cuisine in used_cuisines:
            if len(dinners) < num_dinners - 1:
                continue
        dinners.append(sr)
        selected_names.add(sr.recipe.name)
        if sr.recipe.cuisine:
            used_cuisines.add(sr.recipe.cuisine)

    # Pass 2: Fill lunches from lunch-only
    for sr in lunch_only:
        if len(lunches) >= num_lunches:
            break
        lunches.append(sr)
        selected_names.add(sr.recipe.name)

    # Pass 3: Assign dual-type recipes to whichever slot needs more
    for sr in dual_type:
        if len(dinners) >= num_dinners and len(lunches) >= num_lunches:
            break
        # Prefer the slot with fewer filled entries
        dinners_need = num_dinners - len(dinners)
        lunches_need = num_lunches - len(lunches)
        if lunches_need > 0 and lunches_need >= dinners_need:
            lunches.append(sr)
            selected_names.add(sr.recipe.name)
        elif dinners_need > 0:
            if sr.recipe.cuisine and sr.recipe.cuisine in used_cuisines:
                if dinners_need > 1:
                    # Try next dual recipe for diversity — but track skipped
                    continue
            dinners.append(sr)
            selected_names.add(sr.recipe.name)
            if sr.recipe.cuisine:
                used_cuisines.add(sr.recipe.cuisine)
        elif lunches_need > 0:
            lunches.append(sr)
            selected_names.add(sr.recipe.name)

    # Pass 4: Fill any remaining slots from all remaining recipes (no constraints)
    if len(dinners) < num_dinners or len(lunches) < num_lunches:
        all_remaining = [sr for sr in scored_recipes if sr.recipe.name not in selected_names]
        for sr in all_remaining:
            is_dinner = MealType.DINNER in sr.recipe.meal_types
            is_lunch = MealType.LUNCH in sr.recipe.meal_types
            if is_dinner and len(dinners) < num_dinners:
                dinners.append(sr)
                selected_names.add(sr.recipe.name)
            elif is_lunch and len(lunches) < num_lunches:
                lunches.append(sr)
                selected_names.add(sr.recipe.name)
            if len(dinners) >= num_dinners and len(lunches) >= num_lunches:
                break

    return {"dinners": dinners, "lunches": lunches}
