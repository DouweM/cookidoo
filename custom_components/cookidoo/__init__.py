"""The Cookidoo integration."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import CookidooConfigEntry, CookidooCoordinator
from .services import async_setup_services

PLATFORMS: list[Platform] = [
    Platform.BUTTON,
    Platform.CALENDAR,
    Platform.SENSOR,
    Platform.TODO,
]


async def async_setup_entry(hass: HomeAssistant, entry: CookidooConfigEntry) -> bool:
    """Set up Cookidoo from a config entry."""
    coordinator = CookidooCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    async_setup_services(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: CookidooConfigEntry) -> bool:
    """Unload a config entry and close the SDK client."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.client.aclose()
    return unloaded


async def _async_reload_entry(hass: HomeAssistant, entry: CookidooConfigEntry) -> None:
    """Reload the entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
