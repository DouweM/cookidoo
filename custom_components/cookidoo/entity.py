"""Base entity for the Cookidoo integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import CookidooCoordinator


class CookidooEntity(CoordinatorEntity[CookidooCoordinator]):
    """Base class for Cookidoo entities, attached to the account service device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: CookidooCoordinator, key: str) -> None:
        """Initialise the entity with a stable unique id and device."""
        super().__init__(coordinator)
        entry = coordinator.config_entry
        device_id = entry.unique_id or entry.entry_id
        self._attr_unique_id = f"{device_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name="Cookidoo",
            manufacturer="Vorwerk",
            model="Cookidoo",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=coordinator.client.market.base_url,
        )
