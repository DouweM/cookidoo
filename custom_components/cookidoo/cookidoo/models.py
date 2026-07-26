"""Pydantic v2 models for Cookidoo entities.

Design notes:
- ``populate_by_name=True`` + ``alias`` maps the API's camelCase JSON keys onto
  snake_case attributes; you can construct by either name.
- ``extra='allow'`` keeps any fields the API adds per market/subscription; they
  remain accessible as attributes and via ``model_extra``.
- Field names/aliases were derived from live responses (see ``research/samples``).
"""

from __future__ import annotations

from typing import Annotated, Any, cast

from pydantic import BaseModel, ConfigDict, Field


class _Base(BaseModel):
    """Base model: alias-aware, tolerant of unknown fields."""

    model_config = ConfigDict(populate_by_name=True, extra="allow", protected_namespaces=())


class Asset(_Base):
    """An image asset with per-orientation URLs."""

    type: str | None = None
    square: str | None = None
    portrait: str | None = None
    landscape: str | None = None


class Quantity(_Base):
    """A numeric quantity, optionally a range (``from``/``to``)."""

    value: float | None = None
    to: float | None = None
    from_: Annotated[float | None, Field(alias="from")] = None


class RecipeSummary(_Base):
    """A lightweight recipe reference (search hits, feed tiles, list entries)."""

    id: str
    title: str | None = None
    image: str | None = None
    rating: float | None = None
    number_of_ratings: Annotated[int | None, Field(alias="numberOfRatings")] = None
    total_time: Annotated[int | None, Field(alias="totalTime")] = None
    locale: str | None = None
    language: str | None = None
    descriptive_assets: Annotated[list[Asset], Field(alias="descriptiveAssets")] = []


class Ingredient(_Base):
    """A single recipe/shopping-list ingredient."""

    id: str | None = None
    notation: Annotated[str | None, Field(alias="ingredientNotation")] = None
    primary_notation: Annotated[str | None, Field(alias="primaryNotation")] = None
    is_owned: Annotated[bool | None, Field(alias="isOwned")] = None
    optional: bool | None = None
    quantity: Quantity | None = None
    unit_notation: Annotated[str | None, Field(alias="unitNotation")] = None
    shopping_category_ref: Annotated[str | None, Field(alias="shoppingCategory_ref")] = None
    owned_timestamp: Annotated[int | None, Field(alias="ownedTimestamp")] = None

    @property
    def name(self) -> str | None:
        """Human-readable ingredient name."""
        return self.notation or self.primary_notation


class IngredientGroup(_Base):
    """A titled group of ingredients within a recipe."""

    title: str | None = None
    recipe_ingredients: Annotated[list[Ingredient], Field(alias="recipeIngredients")] = []


class RecipeStep(_Base):
    """A single guided-cooking step."""

    title: str | None = None
    formatted_text: Annotated[str | None, Field(alias="formattedText")] = None


class StepGroup(_Base):
    """A titled group of preparation steps."""

    title: str | None = None
    recipe_steps: Annotated[list[RecipeStep], Field(alias="recipeSteps")] = []


class RecipeTime(_Base):
    """A named duration (e.g. preparation, total, cooking)."""

    type: str | None = None
    comment: str | None = None
    quantity: Quantity | None = None


class ServingSize(_Base):
    """A recipe serving size (quantity + unit)."""

    quantity: Quantity | None = None
    unit_notation: Annotated[str | None, Field(alias="unitNotation")] = None


class Recipe(_Base):
    """A full recipe (from ``recipe:details``)."""

    id: str
    title: str | None = None
    locale: str | None = None
    language: str | None = None
    status: str | None = None
    difficulty: str | None = None
    serving_size: Annotated[ServingSize | None, Field(alias="servingSize")] = None
    times: list[RecipeTime] = []
    tags: list[dict[str, Any]] = []
    categories: list[dict[str, Any]] = []
    thermomix_versions: Annotated[list[str], Field(alias="thermomixVersions")] = []
    recipe_ingredient_groups: Annotated[list[IngredientGroup], Field(alias="recipeIngredientGroups")] = []
    recipe_step_groups: Annotated[list[StepGroup], Field(alias="recipeStepGroups")] = []
    nutrition_groups: Annotated[list[dict[str, Any]], Field(alias="nutritionGroups")] = []
    devices_and_accessories: Annotated[list[dict[str, Any]], Field(alias="devicesAndAccessories")] = []
    descriptive_assets: Annotated[list[Asset], Field(alias="descriptiveAssets")] = []
    cluster: dict[str, Any] | None = None
    markets: list[str] = []


class AdditionalItem(_Base):
    """A free-text shopping-list item (not tied to a recipe)."""

    id: str | None = None
    name: str | None = None
    is_owned: Annotated[bool | None, Field(alias="isOwned")] = None
    owned_timestamp: Annotated[int | None, Field(alias="ownedTimestamp")] = None


class ShoppingList(_Base):
    """The shopping list: recipe ingredients + free-text additional items."""

    recipes: list[dict[str, Any]] = []
    customer_recipes: Annotated[list[dict[str, Any]], Field(alias="customerRecipes")] = []
    additional_items: Annotated[list[AdditionalItem], Field(alias="additionalItems")] = []

    def ingredients(self) -> list[Ingredient]:
        """Flatten every shopping-list recipe's ingredients into a single list.

        On the shopping list each ``recipeIngredientGroups`` entry is itself an
        ingredient object (a flat list), unlike a recipe-detail response where
        groups nest ``recipeIngredients``. Both shapes are handled.
        """
        out: list[Ingredient] = []
        for r in (*self.recipes, *self.customer_recipes):
            groups = r.get("recipeIngredientGroups")
            if not isinstance(groups, list):
                continue
            for g in cast("list[Any]", groups):
                if not isinstance(g, dict):
                    continue
                grp = cast("dict[str, Any]", g)
                nested = grp.get("recipeIngredients") or grp.get("ingredients")
                if isinstance(nested, list):
                    out.extend(Ingredient.model_validate(i) for i in cast("list[Any]", nested))
                else:
                    out.append(Ingredient.model_validate(grp))
        return out


class Subscription(_Base):
    """A Cookidoo subscription/ownership record."""

    active: Annotated[bool, Field(alias="subscriptionActive")] = False
    auto_renewing: Annotated[bool | None, Field(alias="autoRenewingActive")] = None
    type: str | None = None
    status: str | None = None
    level: Annotated[str | None, Field(alias="subscriptionLevel")] = None
    source: Annotated[str | None, Field(alias="subscriptionSource")] = None
    product: str | None = None
    start_date: Annotated[str | None, Field(alias="startDate")] = None
    end_date: Annotated[str | None, Field(alias="endDate")] = None


class CalendarDay(_Base):
    """One day of the meal planner."""

    day_key: Annotated[str | None, Field(alias="dayKey")] = None
    recipes: list[RecipeSummary] = []
    customer_recipe_ids: Annotated[list[str], Field(alias="customerRecipeIds")] = []


class CalendarWeek(_Base):
    """A meal-planner week (``my-week-enhanced``)."""

    my_days: Annotated[list[CalendarDay], Field(alias="myDays")] = []
    recipe_count: Annotated[int | None, Field(alias="recipeCount")] = None
    user_id: Annotated[str | None, Field(alias="userId")] = None


class Chapter(_Base):
    """A titled chapter within a collection."""

    title: str | None = None
    recipes: list[RecipeSummary] = []
    recipe_ids: Annotated[list[str], Field(alias="recipeIds")] = []


class Collection(_Base):
    """A recipe collection / list (custom, managed, or bookmark)."""

    id: str | None = None
    title: str | None = None
    author: str | None = None
    list_type: Annotated[str | None, Field(alias="listType")] = None
    chapters: list[Chapter] = []
    recipes: list[RecipeSummary] = []

    def all_recipes(self) -> list[RecipeSummary]:
        """Return recipes from the collection body and all chapters."""
        out = list(self.recipes)
        for ch in self.chapters:
            out.extend(ch.recipes)
        return out


class CustomRecipeContent(_Base):
    """The schema.org-style body of a user-created recipe."""

    name: str | None = None
    image: str | None = None
    total_time: Annotated[str | int | None, Field(alias="totalTime")] = None
    prep_time: Annotated[str | int | None, Field(alias="prepTime")] = None
    recipe_ingredient: Annotated[list[Any], Field(alias="recipeIngredient")] = []
    recipe_instructions: Annotated[list[Any], Field(alias="recipeInstructions")] = []
    recipe_yield: Annotated[dict[str, Any] | None, Field(alias="recipeYield")] = None


class CustomRecipe(_Base):
    """A user-created ("customer") recipe."""

    id: Annotated[str | None, Field(alias="recipeId")] = None
    author_id: Annotated[str | None, Field(alias="authorId")] = None
    status: str | None = None
    work_status: Annotated[str | None, Field(alias="workStatus")] = None
    created_at: Annotated[str | None, Field(alias="createdAt")] = None
    modified_at: Annotated[str | None, Field(alias="modifiedAt")] = None
    content: Annotated[CustomRecipeContent | None, Field(alias="recipeContent")] = None

    @property
    def name(self) -> str | None:
        """The recipe's display name, if present."""
        return self.content.name if self.content else None


class ForYouStripe(_Base):
    """A single personalized carousel ("stripe") in the For You feed."""

    topic: Annotated[str | None, Field(alias="stripeTopic")] = None
    title: Annotated[str | None, Field(alias="stripeTitle")] = None
    position: Annotated[int | None, Field(alias="stripePosition")] = None
    recipes: list[RecipeSummary] = []


class ForYouFeed(_Base):
    """The personalized For You feed (a list of stripes)."""

    consent: bool | None = None
    stripes: list[ForYouStripe] = []


class AggregatedRating(_Base):
    """A recipe's aggregated community rating."""

    rating: Annotated[float | None, Field(alias="aggregatedRating")] = None
    count: Annotated[int | None, Field(alias="numberOfRatings")] = None
    updated_at: Annotated[str | None, Field(alias="updatedAt")] = None


class SavedSearch(_Base):
    """A saved search stored on the community profile."""

    id: str | None = None
    search: dict[str, Any] | None = None


class CommunityProfile(_Base):
    """The user's community profile (username, preferences, saved searches)."""

    id: str | None = None
    is_public: Annotated[bool | None, Field(alias="isPublic")] = None
    food_preferences: Annotated[list[str], Field(alias="foodPreferences")] = []
    saved_searches: Annotated[list[SavedSearch], Field(alias="savedSearches")] = []
    thermomixes: list[dict[str, Any]] = []
    user_info: Annotated[dict[str, Any], Field(alias="userInfo")] = {}

    @property
    def username(self) -> str | None:
        """The public username, if set."""
        value = self.user_info.get("username")
        return value if isinstance(value, str) else None

    @property
    def picture(self) -> str | None:
        """The profile picture URL, if set."""
        value = self.user_info.get("picture")
        return value if isinstance(value, str) else None


class RecipeNote(_Base):
    """A personal note attached to a recipe."""

    note_id: Annotated[str | None, Field(alias="noteId")] = None
    recipe_id: Annotated[str | None, Field(alias="recipeId")] = None
    user_id: Annotated[str | None, Field(alias="userId")] = None
    text: str | None = None
    modified_at: Annotated[str | None, Field(alias="modifiedAt")] = None


class CookingStatus(_Base):
    """A live cooking-status frame pushed from a connected Thermomix (via FCM).

    Firebase data messages are string-valued, so raw fields are strings; the
    ``remaining_seconds`` / ``time_estimated`` helpers give typed views.
    """

    id: str | None = None
    state: str | None = None  # running | paused | done | acknowledged | stale
    device_id: Annotated[str | None, Field(alias="deviceId")] = None
    recipe_id: Annotated[str | None, Field(alias="recipeId")] = None
    recipe_type: Annotated[str | None, Field(alias="recipeType")] = None  # VorwerkRecipe | CreatedRecipe
    remaining_duration: Annotated[str | None, Field(alias="remainingDuration")] = None
    is_time_estimated: Annotated[str | None, Field(alias="isTimeEstimated")] = None
    primary_info: Annotated[str | None, Field(alias="primaryInfo")] = None
    secondary_info: Annotated[str | None, Field(alias="secondaryInfo")] = None
    leading: str | None = None
    trailing_text: Annotated[str | None, Field(alias="trailingText")] = None
    message_title: Annotated[str | None, Field(alias="messageTitle")] = None
    message_body: Annotated[str | None, Field(alias="messageBody")] = None
    message_criticality: Annotated[str | None, Field(alias="messageCriticality")] = None  # info | warning | error
    completed_date: Annotated[str | None, Field(alias="completedDate")] = None
    stale_date: Annotated[str | None, Field(alias="staleDate")] = None

    @property
    def remaining_seconds(self) -> int | None:
        """Remaining time in seconds, if numeric."""
        try:
            return int(self.remaining_duration) if self.remaining_duration is not None else None
        except TypeError, ValueError:
            return None

    @property
    def time_estimated(self) -> bool:
        """Whether the remaining time is an estimate."""
        return str(self.is_time_estimated).lower() == "true"

    @property
    def finished(self) -> bool:
        """Whether cooking has completed."""
        return self.state in {"done", "acknowledged"}


class SearchResult(_Base):
    """A recipe search response."""

    data: list[RecipeSummary] = []
    total: int | None = None

    @property
    def recipes(self) -> list[RecipeSummary]:
        """The list of matched recipes."""
        return self.data
