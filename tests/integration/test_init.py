"""Tests for setting up and unloading the Cookidoo config entry."""

from __future__ import annotations

from unittest.mock import MagicMock

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.cookidoo.const import DOMAIN


async def test_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    setup_integration,
) -> None:
    """The entry loads, creates the service device, and exposes its entities."""
    await setup_integration(hass, mock_config_entry, mock_client)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(identifiers={(DOMAIN, "user-uuid")})
    assert device is not None
    assert device.manufacturer == "Vorwerk"

    # A representative entity from each platform exists.
    assert hass.states.get("todo.cookidoo_shopping_list") is not None
    assert hass.states.get("calendar.cookidoo_meal_plan") is not None
    assert hass.states.get("sensor.cookidoo_planned_meals") is not None


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    setup_integration,
) -> None:
    """Unloading the entry closes the SDK client."""
    await setup_integration(hass, mock_config_entry, mock_client)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_client.aclose.assert_awaited_once()
