"""Sensor platform for the Cookidoo integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util import dt as dt_util

from .coordinator import CookidooConfigEntry, CookidooCoordinator, CookidooData
from .entity import CookidooEntity

# Subscription tiers exposed by the ENUM sensor.
SUBSCRIPTION_OPTIONS = ["free", "trial", "premium", "regular", "other"]


def _subscription_type(data: CookidooData) -> str:
    """Map the subscription type/level onto a known ENUM option."""
    subscription = data.subscription
    if subscription is None:
        return "free"
    raw = subscription.type or subscription.level
    if not raw:
        return "free"
    value = raw.lower()
    return value if value in SUBSCRIPTION_OPTIONS else "other"


def _subscription_status(data: CookidooData) -> str | None:
    """Return the subscription status, if any."""
    subscription = data.subscription
    return subscription.status if subscription else None


def _subscription_expires(data: CookidooData) -> datetime | None:
    """Parse the subscription end date into an aware datetime."""
    subscription = data.subscription
    if subscription is None or not subscription.end_date:
        return None
    return dt_util.parse_datetime(subscription.end_date)


def _planned_meals(data: CookidooData) -> int:
    """Return the number of recipes planned for the current week."""
    week = data.week
    if week is None:
        return 0
    if week.recipe_count is not None:
        return week.recipe_count
    return sum(len(day.recipes) for day in week.my_days)


def _thermomix(data: CookidooData) -> str | None:
    """Return the primary Thermomix version, if any."""
    return data.thermomix_versions[0] if data.thermomix_versions else None


@dataclass(frozen=True, kw_only=True)
class CookidooSensorEntityDescription(SensorEntityDescription):
    """Describes a Cookidoo sensor."""

    value_fn: Callable[[CookidooData], StateType | datetime]
    attributes_fn: Callable[[CookidooData], dict[str, Any]] | None = None


SENSORS: tuple[CookidooSensorEntityDescription, ...] = (
    CookidooSensorEntityDescription(
        key="subscription_type",
        translation_key="subscription_type",
        device_class=SensorDeviceClass.ENUM,
        options=SUBSCRIPTION_OPTIONS,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_subscription_type,
    ),
    CookidooSensorEntityDescription(
        key="subscription_status",
        translation_key="subscription_status",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_subscription_status,
    ),
    CookidooSensorEntityDescription(
        key="subscription_expires",
        translation_key="subscription_expires",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_subscription_expires,
    ),
    CookidooSensorEntityDescription(
        key="shopping_list_items",
        translation_key="shopping_list_items",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="items",
        icon="mdi:cart",
        value_fn=lambda data: len(data.ingredients),
    ),
    CookidooSensorEntityDescription(
        key="additional_items",
        translation_key="additional_items",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="items",
        icon="mdi:cart-plus",
        value_fn=lambda data: len(data.additional_items),
    ),
    CookidooSensorEntityDescription(
        key="planned_meals",
        translation_key="planned_meals",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="meals",
        icon="mdi:calendar-week",
        value_fn=_planned_meals,
    ),
    CookidooSensorEntityDescription(
        key="custom_recipes",
        translation_key="custom_recipes",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="recipes",
        icon="mdi:notebook",
        value_fn=lambda data: len(data.custom_recipes),
    ),
    CookidooSensorEntityDescription(
        key="thermomix",
        translation_key="thermomix",
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:blender",
        value_fn=_thermomix,
        attributes_fn=lambda data: {"versions": data.thermomix_versions},
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CookidooConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Cookidoo sensors from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(CookidooSensor(coordinator, description) for description in SENSORS)


class CookidooSensor(CookidooEntity, SensorEntity):
    """A generic Cookidoo sensor backed by a value function."""

    entity_description: CookidooSensorEntityDescription

    def __init__(
        self,
        coordinator: CookidooCoordinator,
        description: CookidooSensorEntityDescription,
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> StateType | datetime:
        """Return the sensor's current value."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional state attributes, if the description provides them."""
        if self.entity_description.attributes_fn is None:
            return None
        return self.entity_description.attributes_fn(self.coordinator.data)
