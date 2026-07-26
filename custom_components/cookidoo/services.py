"""Services for the Cookidoo integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

import voluptuous as vol
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_DATE,
    ATTR_ITEMS,
    ATTR_LIMIT,
    ATTR_QUERY,
    ATTR_RECIPE_IDS,
    DOMAIN,
    SERVICE_ADD_ITEMS,
    SERVICE_ADD_RECIPE_TO_PLAN,
    SERVICE_ADD_RECIPE_TO_SHOPPING_LIST,
    SERVICE_CLEAR_SHOPPING_LIST,
    SERVICE_REMOVE_RECIPE_FROM_PLAN,
    SERVICE_SEARCH_RECIPES,
)
from .cookidoo import CookidooError

if TYPE_CHECKING:
    from .coordinator import CookidooCoordinator

ATTR_RECIPE_ID = "recipe_id"
DEFAULT_SEARCH_LIMIT = 10

ADD_RECIPE_TO_SHOPPING_LIST_SCHEMA = vol.Schema({vol.Required(ATTR_RECIPE_IDS): vol.All(cv.ensure_list, [cv.string])})

ADD_ITEMS_SCHEMA = vol.Schema({vol.Required(ATTR_ITEMS): vol.All(cv.ensure_list, [cv.string])})

ADD_RECIPE_TO_PLAN_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DATE): cv.date,
        vol.Required(ATTR_RECIPE_IDS): vol.All(cv.ensure_list, [cv.string]),
    }
)

REMOVE_RECIPE_FROM_PLAN_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DATE): cv.date,
        vol.Required(ATTR_RECIPE_ID): cv.string,
    }
)

CLEAR_SHOPPING_LIST_SCHEMA = vol.Schema({})

SEARCH_RECIPES_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_QUERY): cv.string,
        vol.Optional(ATTR_LIMIT, default=DEFAULT_SEARCH_LIMIT): cv.positive_int,
    }
)


def _coordinator(hass: HomeAssistant) -> CookidooCoordinator:
    """Return the coordinator from the single loaded config entry."""
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    if not entries:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="no_config_entry",
        )
    return entries[0].runtime_data


def async_setup_services(hass: HomeAssistant) -> None:
    """Register the Cookidoo services (idempotent)."""
    if hass.services.has_service(DOMAIN, SERVICE_CLEAR_SHOPPING_LIST):
        return

    async def async_add_recipe_to_shopping_list(call: ServiceCall) -> None:
        coordinator = _coordinator(hass)
        try:
            await coordinator.client.shopping.add_recipes(call.data[ATTR_RECIPE_IDS])
        except CookidooError as err:
            raise HomeAssistantError(str(err)) from err
        await coordinator.async_request_refresh()

    async def async_add_items(call: ServiceCall) -> None:
        coordinator = _coordinator(hass)
        try:
            await coordinator.client.shopping.add_additional_items(call.data[ATTR_ITEMS])
        except CookidooError as err:
            raise HomeAssistantError(str(err)) from err
        await coordinator.async_request_refresh()

    async def async_add_recipe_to_plan(call: ServiceCall) -> None:
        coordinator = _coordinator(hass)
        try:
            await coordinator.client.planner.add_recipes(call.data[ATTR_DATE], call.data[ATTR_RECIPE_IDS])
        except CookidooError as err:
            raise HomeAssistantError(str(err)) from err
        await coordinator.async_request_refresh()

    async def async_remove_recipe_from_plan(call: ServiceCall) -> None:
        coordinator = _coordinator(hass)
        try:
            await coordinator.client.planner.remove_recipe(call.data[ATTR_DATE], call.data[ATTR_RECIPE_ID])
        except CookidooError as err:
            raise HomeAssistantError(str(err)) from err
        await coordinator.async_request_refresh()

    async def async_clear_shopping_list(call: ServiceCall) -> None:
        coordinator = _coordinator(hass)
        try:
            await coordinator.client.shopping.clear()
        except CookidooError as err:
            raise HomeAssistantError(str(err)) from err
        await coordinator.async_request_refresh()

    async def async_search_recipes(call: ServiceCall) -> ServiceResponse:
        coordinator = _coordinator(hass)
        try:
            result = await coordinator.client.search.recipes(call.data[ATTR_QUERY], limit=call.data[ATTR_LIMIT])
        except CookidooError as err:
            raise HomeAssistantError(str(err)) from err
        recipes: list[dict[str, Any]] = [
            {
                "id": recipe.id,
                "title": recipe.title,
                "rating": recipe.rating,
                "total_time": recipe.total_time,
                "image": recipe.image,
            }
            for recipe in result.recipes
        ]
        return cast("ServiceResponse", {"recipes": recipes})

    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_RECIPE_TO_SHOPPING_LIST,
        async_add_recipe_to_shopping_list,
        schema=ADD_RECIPE_TO_SHOPPING_LIST_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_ITEMS,
        async_add_items,
        schema=ADD_ITEMS_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_RECIPE_TO_PLAN,
        async_add_recipe_to_plan,
        schema=ADD_RECIPE_TO_PLAN_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REMOVE_RECIPE_FROM_PLAN,
        async_remove_recipe_from_plan,
        schema=REMOVE_RECIPE_FROM_PLAN_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CLEAR_SHOPPING_LIST,
        async_clear_shopping_list,
        schema=CLEAR_SHOPPING_LIST_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SEARCH_RECIPES,
        async_search_recipes,
        schema=SEARCH_RECIPES_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
