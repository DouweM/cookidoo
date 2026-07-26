"""Diagnostics support for the Cookidoo integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import CONF_PASSWORD
from .coordinator import CookidooConfigEntry

TO_REDACT = {CONF_PASSWORD}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: CookidooConfigEntry) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    data = coordinator.data

    return {
        "entry": async_redact_data(entry.data, TO_REDACT),
        "options": dict(entry.options),
        "data": {
            "ingredients": len(data.ingredients),
            "additional_items": len(data.additional_items),
            "custom_recipes": len(data.custom_recipes),
            "thermomix_versions": data.thermomix_versions,
            "week_days": len(data.week.my_days) if data.week else 0,
            "subscription": (data.subscription.model_dump() if data.subscription else None),
        },
    }
