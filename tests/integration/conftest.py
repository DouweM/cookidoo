"""Shared fixtures for the Cookidoo integration tests."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.cookidoo.const import (
    CONF_EMAIL,
    CONF_MARKET,
    CONF_PASSWORD,
    DOMAIN,
)
from custom_components.cookidoo.cookidoo import UserInfo, get_market
from custom_components.cookidoo.cookidoo.models import (
    CalendarDay,
    CalendarWeek,
    CustomRecipe,
    RecipeSummary,
    ShoppingList,
    Subscription,
)


@pytest.fixture(autouse=True)
def _auto_enable(enable_custom_integrations):
    """Enable loading the Cookidoo custom integration in every test."""
    yield


@pytest.fixture
def mock_client() -> MagicMock:
    """Return a MagicMock standing in for a ``CookidooClient`` instance.

    Async read methods return real SDK model instances so the coordinator and
    entities exercise the genuine parsing/derivation logic; mutation methods are
    bare ``AsyncMock``s whose calls can be asserted.
    """
    client = MagicMock()

    # Market / language are read synchronously by the entity + calendar.
    client.market = get_market("mx")
    client.language = "es-MX"

    # --- auth / lifecycle -------------------------------------------------
    client.login = AsyncMock(return_value=None)
    client.get_user_info = AsyncMock(return_value=UserInfo(dcid="user-uuid", email="me@example.com"))
    client.aclose = AsyncMock(return_value=None)

    # --- snapshot reads (asyncio.gather in the coordinator) ---------------
    shopping_list = ShoppingList(
        recipes=[
            {
                "recipeIngredientGroups": [
                    {
                        "id": "i1",
                        "ingredientNotation": "Tomatoes",
                        "isOwned": False,
                        "unitNotation": "kg",
                        "quantity": {"value": 2},
                    },
                    {
                        "id": "i2",
                        "ingredientNotation": "Onions",
                        "isOwned": True,
                    },
                ]
            }
        ],
        additionalItems=[{"id": "a1", "name": "Napkins", "isOwned": False}],
    )
    client.shopping.get_list = AsyncMock(return_value=shopping_list)
    client.profile.active_subscription = AsyncMock(
        return_value=Subscription(
            subscriptionActive=True,
            type="REGULAR",
            status="ACTIVE",
            endDate="2027-07-25T23:59:00Z",
        )
    )
    client.planner.get_week = AsyncMock(
        return_value=CalendarWeek(
            myDays=[
                CalendarDay(
                    dayKey="2026-07-27",
                    recipes=[RecipeSummary(id="r1", title="Tacos")],
                )
            ],
            recipeCount=1,
        )
    )
    client.devices.thermomix_versions = AsyncMock(return_value=["TM6"])
    client.custom_recipes.list = AsyncMock(
        return_value=[CustomRecipe(recipeId="c1", recipeContent={"name": "Gazpacho"})]
    )

    # --- mutations --------------------------------------------------------
    client.shopping.add_recipes = AsyncMock(return_value=None)
    client.shopping.clear = AsyncMock(return_value=None)
    client.shopping.set_ingredient_ownership = AsyncMock(return_value=None)
    client.shopping.add_additional_items = AsyncMock(return_value=None)
    client.shopping.edit_additional_items = AsyncMock(return_value=None)
    client.shopping.set_additional_item_ownership = AsyncMock(return_value=None)
    client.shopping.remove_additional_items = AsyncMock(return_value=None)
    client.planner.add_recipes = AsyncMock(return_value=None)
    client.planner.remove_recipe = AsyncMock(return_value=None)
    client.search.recipes = AsyncMock(return_value=MagicMock(recipes=[]))

    return client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a Cookidoo config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_EMAIL: "me@example.com",
            CONF_PASSWORD: "pw",
            CONF_MARKET: "mx",
        },
        unique_id="user-uuid",
    )


@pytest.fixture
def setup_integration() -> Callable[[HomeAssistant, MockConfigEntry, MagicMock], Awaitable[MockConfigEntry]]:
    """Return a helper that sets the integration up with a patched SDK client.

    Both ``CookidooClient`` references (coordinator + config flow) are patched to
    return the provided ``mock_client``.
    """

    async def _setup(hass: HomeAssistant, entry: MockConfigEntry, mock_client: MagicMock) -> MockConfigEntry:
        entry.add_to_hass(hass)
        with (
            patch(
                "custom_components.cookidoo.coordinator.CookidooClient",
                return_value=mock_client,
            ),
            patch(
                "custom_components.cookidoo.config_flow.CookidooClient",
                return_value=mock_client,
            ),
        ):
            await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()
        return entry

    return _setup
