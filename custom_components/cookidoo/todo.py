"""Todo platform for the Cookidoo integration."""

from __future__ import annotations

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .cookidoo.models import AdditionalItem, Ingredient
from .coordinator import CookidooConfigEntry, CookidooCoordinator
from .entity import CookidooEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CookidooConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Cookidoo todo lists."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            CookidooShoppingListTodoListEntity(coordinator),
            CookidooAdditionalItemsTodoListEntity(coordinator),
        ]
    )


def _ingredient_summary(ingredient: Ingredient) -> str:
    """Build a display summary, prefixing quantity + unit when present."""
    name = ingredient.name or ""
    quantity = ingredient.quantity
    parts: list[str] = []
    if quantity is not None:
        if quantity.value is not None:
            parts.append(_format_number(quantity.value))
        elif quantity.from_ is not None or quantity.to is not None:
            bounds = [_format_number(bound) for bound in (quantity.from_, quantity.to) if bound is not None]
            parts.append("-".join(bounds))
    if ingredient.unit_notation:
        parts.append(ingredient.unit_notation)
    if name:
        parts.append(name)
    return " ".join(parts).strip() or name


def _format_number(value: float) -> str:
    """Render a quantity without a trailing ``.0`` for whole numbers."""
    if value == int(value):
        return str(int(value))
    return str(value)


class CookidooShoppingListTodoListEntity(CookidooEntity, TodoListEntity):
    """The recipe-derived shopping list (ingredients).

    Ingredients come from recipes on the meal plan, so items cannot be created
    or deleted here; only their owned/unowned state can be toggled.
    """

    _attr_translation_key = "shopping_list"
    _attr_supported_features = TodoListEntityFeature.UPDATE_TODO_ITEM

    def __init__(self, coordinator: CookidooCoordinator) -> None:
        """Initialise the shopping list entity."""
        super().__init__(coordinator, "shopping_list")

    @property
    def todo_items(self) -> list[TodoItem]:
        """Return the ingredients as todo items."""
        return [
            TodoItem(
                uid=ingredient.id,
                summary=_ingredient_summary(ingredient),
                status=(TodoItemStatus.COMPLETED if ingredient.is_owned else TodoItemStatus.NEEDS_ACTION),
            )
            for ingredient in self.coordinator.data.ingredients
            if ingredient.id is not None
        ]

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Toggle an ingredient's owned state (rename/delete unsupported)."""
        if item.uid is None:
            return
        owned = item.status == TodoItemStatus.COMPLETED
        await self.coordinator.client.shopping.set_ingredient_ownership([(item.uid, owned)])
        await self.coordinator.async_request_refresh()


class CookidooAdditionalItemsTodoListEntity(CookidooEntity, TodoListEntity):
    """The free-text additional purchases list (full CRUD)."""

    _attr_translation_key = "additional_items"
    _attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM
        | TodoListEntityFeature.UPDATE_TODO_ITEM
        | TodoListEntityFeature.DELETE_TODO_ITEM
    )

    def __init__(self, coordinator: CookidooCoordinator) -> None:
        """Initialise the additional items entity."""
        super().__init__(coordinator, "additional_items")

    @property
    def todo_items(self) -> list[TodoItem]:
        """Return the additional items as todo items."""
        return [
            TodoItem(
                uid=item.id,
                summary=item.name or "",
                status=(TodoItemStatus.COMPLETED if item.is_owned else TodoItemStatus.NEEDS_ACTION),
            )
            for item in self.coordinator.data.additional_items
            if item.id is not None
        ]

    async def async_create_todo_item(self, item: TodoItem) -> None:
        """Add a new free-text item."""
        if not item.summary:
            return
        await self.coordinator.client.shopping.add_additional_items([item.summary])
        await self.coordinator.async_request_refresh()

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Update an item's name and/or owned state."""
        if item.uid is None:
            return
        current = self._item_by_uid(item.uid)
        if current is not None and item.summary is not None and item.summary != current.name:
            await self.coordinator.client.shopping.edit_additional_items(
                [AdditionalItem(id=item.uid, name=item.summary)]
            )
        new_owned = item.status == TodoItemStatus.COMPLETED
        if current is None or new_owned != bool(current.is_owned):
            await self.coordinator.client.shopping.set_additional_item_ownership([(item.uid, new_owned)])
        await self.coordinator.async_request_refresh()

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        """Remove items from the additional purchases list."""
        await self.coordinator.client.shopping.remove_additional_items(uids)
        await self.coordinator.async_request_refresh()

    def _item_by_uid(self, uid: str) -> AdditionalItem | None:
        """Return the coordinator's additional item matching ``uid``."""
        for item in self.coordinator.data.additional_items:
            if item.id == uid:
                return item
        return None
