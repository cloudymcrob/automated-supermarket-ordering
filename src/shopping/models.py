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


class CookStyle(Enum):
    QUICK = "Quick"    # ≤40 min start to finish
    BATCH = "Batch"    # Multiple portions, leftovers/freeze
    BOTH = "Both"      # Quick but scales well for batch


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
    notes: str = ""
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
    notes: str = ""


@dataclass
class Recipe:
    """A recipe from the Recipes database."""
    name: str
    cuisine: str = ""
    meal_types: list[MealType] = field(default_factory=lambda: [MealType.DINNER])
    servings: int = 2
    num_portions_per_quantity: float | None = None
    quantity_multiplier: float = 1.0
    cook_style: CookStyle = CookStyle.QUICK
    prep_time_mins: int = 0
    cook_time_mins: int = 0
    last_cooked: date | None = None
    times_cooked: int = 0
    rating: int | None = None
    tags: list[str] = field(default_factory=list)
    active: bool = True
    source_url: str = ""
    instructions: str = ""
    ingredients: list[RecipeIngredient] = field(default_factory=list)
    notes: str = ""
    notion_id: str | None = None

    @property
    def total_time_mins(self) -> int | None:
        if self.prep_time_mins is None and self.cook_time_mins is None:
            return None
        return (self.prep_time_mins or 0) + (self.cook_time_mins or 0)

    @property
    def effective_portions_per_quantity(self) -> float:
        """Portions produced at quantity_multiplier=1.

        Uses feedback value if set, otherwise defaults to servings / 1.5
        (accounting for large portion sizes).
        """
        if self.num_portions_per_quantity is not None and self.num_portions_per_quantity > 0:
            return self.num_portions_per_quantity
        return self.servings / 1.5

    @property
    def total_portions(self) -> float:
        """Total portions produced at the current quantity_multiplier."""
        return self.effective_portions_per_quantity * self.quantity_multiplier

    @property
    def meals_covered(self) -> int:
        """How many meals (for 2 people) this recipe covers."""
        return max(1, round(self.total_portions / 2))

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
    quantity_multiplier: float = 1.0
    cook_style: CookStyle = CookStyle.QUICK
    days_covered: int = 1
    is_leftover: bool = False
