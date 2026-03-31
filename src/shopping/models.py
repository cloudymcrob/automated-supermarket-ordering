"""Domain models for the automated shopping workflow."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum


class MealType(Enum):
    LUNCH = "Lunch"
    DINNER = "Dinner"


class IngredientCategory(Enum):
    FRUIT_VEG = "Fruit & Veg"
    MEAT = "Meat & Poultry"
    DAIRY_EGGS = "Dairy & Eggs"
    BAKERY = "Bakery"
    FROZEN = "Frozen"
    TINNED_DRIED = "Tinned & Dried"
    CONDIMENTS_SAUCES = "Condiments & Sauces"
    HERBS_SPICES = "Herbs & Spices"
    DRINKS = "Drinks"
    SNACKS = "Snacks"
    HOUSEHOLD = "Household"
    OTHER = "Other"


class PantryStatus(Enum):
    IN_STOCK = "In Stock"
    LOW = "Low"
    OUT = "Out"
    EXPIRED = "Expired"


class StorageLocation(Enum):
    FRIDGE = "Fridge"
    FREEZER = "Freezer"
    CUPBOARD = "Cupboard"
    COUNTER = "Counter"


class PriceSensitivity(Enum):
    CHEAPEST = "Cheapest"
    MID_RANGE = "Mid-range"
    PREMIUM = "Premium"


class Frequency(Enum):
    WEEKLY = "Weekly"
    FORTNIGHTLY = "Fortnightly"
    MONTHLY = "Monthly"
    AS_NEEDED = "As Needed"


# Allergens that must be excluded from direct ingredients
ALLERGENS = frozenset({"nuts", "coconut", "poppy seeds"})

# Expanded allergen keywords for ingredient matching
ALLERGEN_KEYWORDS = frozenset({
    "almond", "almonds", "cashew", "cashews", "walnut", "walnuts",
    "pecan", "pecans", "pistachio", "pistachios", "hazelnut", "hazelnuts",
    "macadamia", "brazil nut", "brazil nuts", "peanut", "peanuts",
    "pine nut", "pine nuts", "nut", "nuts", "mixed nuts",
    "coconut", "coconut milk", "coconut cream", "coconut oil",
    "desiccated coconut", "coconut flour", "coconut water",
    "poppy seed", "poppy seeds",
})


@dataclass
class Ingredient:
    """Master ingredient from the Ingredients database."""
    name: str
    category: IngredientCategory = IngredientCategory.OTHER
    default_unit: str = "whole"
    shelf_life_days: int | None = None
    is_staple: bool = False
    aliases: list[str] = field(default_factory=list)
    notion_id: str | None = None


@dataclass
class RecipeIngredient:
    """An ingredient line within a recipe."""
    ingredient_name: str
    quantity: float
    unit: str
    preparation: str = ""
    optional: bool = False
    recipe_name: str = ""


@dataclass
class Recipe:
    """A recipe from the Recipes database."""
    name: str
    cuisine: str = ""
    meal_types: list[MealType] = field(default_factory=lambda: [MealType.DINNER])
    servings: int = 2
    actual_portions: float | None = None
    prep_time_mins: int = 0
    cook_time_mins: int = 0
    last_cooked: date | None = None
    times_cooked: int = 0
    rating: int | None = None
    tags: list[str] = field(default_factory=list)
    active: bool = True
    ingredients: list[RecipeIngredient] = field(default_factory=list)
    notion_id: str | None = None

    @property
    def total_time_mins(self) -> int:
        return self.prep_time_mins + self.cook_time_mins

    @property
    def servings_multiplier(self) -> float:
        """How much to scale recipe. Uses actual_portions feedback if available,
        otherwise defaults to 1.5x for 2 people with large portions."""
        if self.actual_portions is not None and self.actual_portions > 0:
            # If we know the recipe makes X portions, scale to get 2 large portions
            # Target: 3 portions worth (2 people * 1.5x)
            return 3.0 / self.actual_portions
        return 1.5

    def contains_allergen(self) -> bool:
        """Check if any ingredient directly contains a known allergen."""
        for ing in self.ingredients:
            name_lower = ing.ingredient_name.lower()
            if any(kw in name_lower for kw in ALLERGEN_KEYWORDS):
                return True
        return False


@dataclass
class PantryItem:
    """An item in the pantry inventory."""
    ingredient_name: str
    quantity: float
    unit: str
    expiry_date: date | None = None
    status: PantryStatus = PantryStatus.IN_STOCK
    location: StorageLocation = StorageLocation.CUPBOARD
    notion_id: str | None = None


@dataclass
class ShoppingListItem:
    """An item on the final shopping list."""
    ingredient_name: str
    quantity_needed: float
    unit: str
    category: IngredientCategory = IngredientCategory.OTHER
    preferred_brand: str = ""
    tesco_search_term: str = ""
    price_sensitivity: PriceSensitivity = PriceSensitivity.CHEAPEST
    from_recipes: list[str] = field(default_factory=list)
    is_regular_item: bool = False


@dataclass
class RegularItem:
    """A recurring non-recipe purchase."""
    name: str
    frequency: Frequency = Frequency.WEEKLY
    typical_quantity: float = 1.0
    unit: str = "pack"
    last_ordered: date | None = None
    next_due: date | None = None
    auto_add: bool = True
    notion_id: str | None = None


@dataclass
class ScoredRecipe:
    """A recipe with a computed selection score."""
    recipe: Recipe
    score: float
    reasons: list[str] = field(default_factory=list)


@dataclass
class MealPlanEntry:
    """A single meal slot in a weekly plan."""
    recipe: Recipe
    day: str  # Monday, Tuesday, etc.
    meal: MealType
    servings_multiplier: float = 1.5
