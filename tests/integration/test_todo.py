"""Tests for the Cookidoo todo lists."""

from __future__ import annotations

from unittest.mock import MagicMock

from homeassistant.components.todo import (
    ATTR_ITEM,
    ATTR_RENAME,
    ATTR_STATUS,
    TodoServices,
)
from homeassistant.components.todo import (
    DOMAIN as TODO_DOMAIN,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

SHOPPING_LIST = "todo.cookidoo_shopping_list"
ADDITIONAL_ITEMS = "todo.cookidoo_additional_items"


async def _get_items(hass: HomeAssistant, entity_id: str) -> list[dict]:
    """Return the todo items reported by the ``todo.get_items`` service."""
    result = await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.GET_ITEMS,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
        return_response=True,
    )
    return result[entity_id]["items"]


async def test_shopping_list_items(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    setup_integration,
) -> None:
    """The shopping list shows the flattened ingredients with owned state."""
    await setup_integration(hass, mock_config_entry, mock_client)

    state = hass.states.get(SHOPPING_LIST)
    assert state is not None
    assert state.state == "1"  # one unchecked ingredient (Tomatoes)

    items = await _get_items(hass, SHOPPING_LIST)
    by_uid = {item["uid"]: item for item in items}
    assert by_uid["i1"]["summary"] == "2 kg Tomatoes"
    assert by_uid["i1"]["status"] == "needs_action"
    assert by_uid["i2"]["summary"] == "Onions"
    assert by_uid["i2"]["status"] == "completed"


async def test_shopping_list_toggle(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    setup_integration,
) -> None:
    """Ticking an ingredient calls ``set_ingredient_ownership``."""
    await setup_integration(hass, mock_config_entry, mock_client)

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.UPDATE_ITEM,
        {ATTR_ENTITY_ID: SHOPPING_LIST, ATTR_ITEM: "i1", ATTR_STATUS: "completed"},
        blocking=True,
    )

    mock_client.shopping.set_ingredient_ownership.assert_awaited_once_with([("i1", True)])


async def test_additional_item_create(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    setup_integration,
) -> None:
    """Creating an additional item calls ``add_additional_items``."""
    await setup_integration(hass, mock_config_entry, mock_client)

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.ADD_ITEM,
        {ATTR_ENTITY_ID: ADDITIONAL_ITEMS, ATTR_ITEM: "Milk"},
        blocking=True,
    )

    mock_client.shopping.add_additional_items.assert_awaited_once_with(["Milk"])


async def test_additional_item_delete(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    setup_integration,
) -> None:
    """Deleting an additional item calls ``remove_additional_items`` with its uid."""
    await setup_integration(hass, mock_config_entry, mock_client)

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.REMOVE_ITEM,
        {ATTR_ENTITY_ID: ADDITIONAL_ITEMS, ATTR_ITEM: "Napkins"},
        blocking=True,
    )

    mock_client.shopping.remove_additional_items.assert_awaited_once_with(["a1"])


async def test_additional_item_rename(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    setup_integration,
) -> None:
    """Renaming an additional item calls ``edit_additional_items``."""
    await setup_integration(hass, mock_config_entry, mock_client)

    await hass.services.async_call(
        TODO_DOMAIN,
        TodoServices.UPDATE_ITEM,
        {ATTR_ENTITY_ID: ADDITIONAL_ITEMS, ATTR_ITEM: "Napkins", ATTR_RENAME: "Paper towels"},
        blocking=True,
    )

    mock_client.shopping.edit_additional_items.assert_awaited_once()
