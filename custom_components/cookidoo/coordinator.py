"""DataUpdateCoordinator for the Cookidoo integration."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_EMAIL,
    CONF_LANGUAGE,
    CONF_MARKET,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .cookidoo import CookidooAuthError, CookidooClient, CookidooError
from .cookidoo.models import (
    AdditionalItem,
    CalendarWeek,
    CustomRecipe,
    Ingredient,
    Subscription,
)

_LOGGER = logging.getLogger(__name__)

type CookidooConfigEntry = ConfigEntry[CookidooCoordinator]


@dataclass
class CookidooData:
    """The full snapshot fetched each poll cycle."""

    ingredients: list[Ingredient] = field(default_factory=list)
    additional_items: list[AdditionalItem] = field(default_factory=list)
    subscription: Subscription | None = None
    week: CalendarWeek | None = None
    thermomix_versions: list[str] = field(default_factory=list)
    custom_recipes: list[CustomRecipe] = field(default_factory=list)


class CookidooCoordinator(DataUpdateCoordinator[CookidooData]):
    """Poll Cookidoo and share account data across entities."""

    config_entry: CookidooConfigEntry

    def __init__(self, hass: HomeAssistant, entry: CookidooConfigEntry) -> None:
        """Initialise the coordinator and SDK client."""
        scan_interval = entry.options.get(CONF_SCAN_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=(timedelta(seconds=scan_interval) if scan_interval else DEFAULT_SCAN_INTERVAL),
        )
        self.client = CookidooClient(
            entry.data[CONF_EMAIL],
            entry.data[CONF_PASSWORD],
            market=entry.data[CONF_MARKET],
            language=entry.options.get(CONF_LANGUAGE, entry.data.get(CONF_LANGUAGE)),
            http=get_async_client(hass),
        )

    async def _async_update_data(self) -> CookidooData:
        """Fetch the account snapshot: shopping list, plan, subscription, devices."""
        try:
            shopping, subscription, week, versions, custom = await asyncio.gather(
                self.client.shopping.get_list(),
                self.client.profile.active_subscription(),
                self.client.planner.get_week(),
                self.client.devices.thermomix_versions(),
                self.client.custom_recipes.list(),
            )
        except CookidooAuthError as err:
            raise ConfigEntryAuthFailed(translation_domain=DOMAIN, translation_key="auth_failed") from err
        except CookidooError as err:
            raise UpdateFailed(translation_domain=DOMAIN, translation_key="update_failed") from err

        return CookidooData(
            ingredients=shopping.ingredients(),
            additional_items=shopping.additional_items,
            subscription=subscription,
            week=week,
            thermomix_versions=versions,
            custom_recipes=custom,
        )
