"""Tests for the Cookidoo meal-plan calendar."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

CALENDAR = "calendar.cookidoo_meal_plan"


async def test_calendar_exists(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    setup_integration,
) -> None:
    """The meal-plan calendar entity is created."""
    await setup_integration(hass, mock_config_entry, mock_client)
    assert hass.states.get(CALENDAR) is not None


async def test_get_events(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    setup_integration,
) -> None:
    """``get_events`` returns the planned Tacos event for the week."""
    await setup_integration(hass, mock_config_entry, mock_client)

    result = await hass.services.async_call(
        "calendar",
        "get_events",
        {
            ATTR_ENTITY_ID: CALENDAR,
            "start_date_time": dt_util.as_local(datetime(2026, 7, 26)),
            "end_date_time": dt_util.as_local(datetime(2026, 7, 30)),
        },
        blocking=True,
        return_response=True,
    )

    events = result[CALENDAR]["events"]
    assert len(events) == 1
    assert events[0]["summary"] == "Tacos"
    assert events[0]["start"] == "2026-07-27"
