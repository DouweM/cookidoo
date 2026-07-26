"""Button platform for the Cookidoo integration."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import CookidooConfigEntry, CookidooCoordinator
from .entity import CookidooEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CookidooConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Cookidoo buttons from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities([CookidooButton(coordinator)])


class CookidooButton(CookidooEntity, ButtonEntity):
    """A button that clears the Cookidoo shopping list."""

    _attr_translation_key = "clear_shopping_list"
    _attr_entity_registry_enabled_default = False
    _attr_icon = "mdi:cart-remove"

    def __init__(self, coordinator: CookidooCoordinator) -> None:
        """Initialise the button."""
        super().__init__(coordinator, "clear_shopping_list")

    async def async_press(self) -> None:
        """Clear the shopping list, then refresh the coordinator."""
        await self.coordinator.client.shopping.clear()
        await self.coordinator.async_request_refresh()
