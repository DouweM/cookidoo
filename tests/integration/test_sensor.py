"""Tests for the Cookidoo sensors."""

from __future__ import annotations

from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry


async def test_planned_meals(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    setup_integration,
) -> None:
    """The planned-meals sensor reflects the week's recipe count."""
    await setup_integration(hass, mock_config_entry, mock_client)

    state = hass.states.get("sensor.cookidoo_planned_meals")
    assert state is not None
    assert state.state == "1"


async def test_subscription_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    setup_integration,
) -> None:
    """The subscription sensors map the mocked subscription onto states."""
    await setup_integration(hass, mock_config_entry, mock_client)

    type_state = hass.states.get("sensor.cookidoo_subscription_type")
    assert type_state is not None
    assert type_state.state == "regular"

    status_state = hass.states.get("sensor.cookidoo_subscription_status")
    assert status_state is not None
    assert status_state.state == "ACTIVE"

    expires_state = hass.states.get("sensor.cookidoo_subscription_expires")
    assert expires_state is not None
    assert expires_state.state == "2027-07-25T23:59:00+00:00"


async def test_diagnostic_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    setup_integration,
) -> None:
    """The count/device sensors reflect the mocked snapshot."""
    await setup_integration(hass, mock_config_entry, mock_client)

    assert hass.states.get("sensor.cookidoo_shopping_list_items").state == "2"
    assert hass.states.get("sensor.cookidoo_additional_items").state == "1"
    assert hass.states.get("sensor.cookidoo_custom_recipes").state == "1"

    thermomix = hass.states.get("sensor.cookidoo_thermomix")
    assert thermomix.state == "TM6"
    assert thermomix.attributes["versions"] == ["TM6"]
