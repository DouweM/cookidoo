"""Constants for the Cookidoo integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "cookidoo"

CONF_EMAIL: Final = "email"
CONF_PASSWORD: Final = "password"
CONF_MARKET: Final = "market"
CONF_LANGUAGE: Final = "language"

CONF_SCAN_INTERVAL: Final = "scan_interval"
DEFAULT_SCAN_INTERVAL: Final = timedelta(seconds=90)
MIN_SCAN_INTERVAL: Final = 30
MAX_SCAN_INTERVAL: Final = 3600

# Service names
SERVICE_ADD_RECIPE_TO_SHOPPING_LIST: Final = "add_recipe_to_shopping_list"
SERVICE_ADD_ITEMS: Final = "add_items"
SERVICE_ADD_RECIPE_TO_PLAN: Final = "add_recipe_to_plan"
SERVICE_REMOVE_RECIPE_FROM_PLAN: Final = "remove_recipe_from_plan"
SERVICE_SEARCH_RECIPES: Final = "search_recipes"
SERVICE_CLEAR_SHOPPING_LIST: Final = "clear_shopping_list"

ATTR_RECIPE_IDS: Final = "recipe_ids"
ATTR_ITEMS: Final = "items"
ATTR_DATE: Final = "date"
ATTR_QUERY: Final = "query"
ATTR_LIMIT: Final = "limit"
ATTR_CONFIG_ENTRY_ID: Final = "config_entry_id"
