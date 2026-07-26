"""Calendar platform for the Cookidoo integration."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .cookidoo.models import CalendarWeek, RecipeSummary
from .coordinator import CookidooConfigEntry, CookidooCoordinator
from .entity import CookidooEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CookidooConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Cookidoo meal-plan calendar."""
    coordinator = entry.runtime_data
    async_add_entities([CookidooCalendarEntity(coordinator)])


class CookidooCalendarEntity(CookidooEntity, CalendarEntity):
    """A read-only calendar of the Cookidoo weekly meal plan."""

    _attr_translation_key = "meal_plan"

    def __init__(self, coordinator: CookidooCoordinator) -> None:
        """Initialise the meal-plan calendar entity."""
        super().__init__(coordinator, "meal_plan")

    def _recipe_url(self, recipe: RecipeSummary) -> str:
        """Build a deep link to the recipe on the Cookidoo site."""
        base_url = self.coordinator.client.market.base_url
        lang = self.coordinator.client.language
        return f"{base_url}/recipes/recipe/{lang}/{recipe.id}"

    def _recipe_event(self, day_key: str, recipe: RecipeSummary) -> CalendarEvent:
        """Build an all-day :class:`CalendarEvent` for one planned recipe."""
        start = date.fromisoformat(day_key)
        description_parts: list[str] = []
        if recipe.rating is not None:
            description_parts.append(f"Rating: {recipe.rating}")
        if recipe.total_time is not None:
            description_parts.append(f"Total time: {recipe.total_time}")
        if recipe.descriptive_assets and recipe.descriptive_assets[0].square:
            description_parts.append(recipe.descriptive_assets[0].square)
        return CalendarEvent(
            start=start,
            end=start + timedelta(days=1),
            summary=recipe.title or "",
            description="\n".join(description_parts) or None,
            location=self._recipe_url(recipe),
            uid=f"{day_key}_{recipe.id}",
        )

    def _week_events(self, week: CalendarWeek | None) -> list[CalendarEvent]:
        """Expand a meal-plan week into one all-day event per recipe per day."""
        events: list[CalendarEvent] = []
        if week is None:
            return events
        for day in week.my_days:
            if not day.day_key:
                continue
            for recipe in day.recipes:
                events.append(self._recipe_event(day.day_key, recipe))
        return events

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming (or current) event from the cached week."""
        today = dt_util.now().date()
        upcoming = [
            event for event in self._week_events(self.coordinator.data.week) if _event_date(event.start) >= today
        ]
        if not upcoming:
            return None
        return min(upcoming, key=lambda event: _event_date(event.start))

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Return events overlapping the [start_date, end_date] range.

        Uses the coordinator's cached week and fetches any adjacent weeks the
        range extends into via ``planner.get_week``.
        """
        range_start = dt_util.as_local(start_date).date()
        range_end = dt_util.as_local(end_date).date()

        events: dict[str, CalendarEvent] = {}
        covered: set[str] = set()

        def add_week(week: CalendarWeek | None) -> None:
            if week is None:
                return
            for day in week.my_days:
                if day.day_key:
                    covered.add(day.day_key)
            for event in self._week_events(week):
                if event.uid is not None:
                    events[event.uid] = event

        add_week(self.coordinator.data.week)

        day = range_start
        while day <= range_end:
            if day.isoformat() not in covered:
                add_week(await self.coordinator.client.planner.get_week(day))
            day += timedelta(days=1)

        return sorted(
            (event for event in events.values() if range_start <= _event_date(event.start) <= range_end),
            key=lambda event: _event_date(event.start),
        )


def _event_date(value: date | datetime) -> date:
    """Return the plain date for an all-day event's start."""
    if isinstance(value, datetime):
        return value.date()
    return value
