"""Feature resource clients. Each wraps a group of HAL link relations.

Mutating request bodies/verbs mirror the reverse-engineered app contract
(see ``research/re/*.md``); read endpoints were verified against live responses.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections.abc import AsyncGenerator, Sequence
from datetime import UTC, date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from . import const
from .exceptions import CookidooError
from .models import (
    AdditionalItem,
    AggregatedRating,
    CalendarDay,
    CalendarWeek,
    Collection,
    CommunityProfile,
    CookingStatus,
    CustomRecipe,
    ForYouFeed,
    Recipe,
    RecipeNote,
    RecipeSummary,
    SearchResult,
    ShoppingList,
    Subscription,
)

if TYPE_CHECKING:
    from .client import CookidooClient

R = const.Rel

# sentinel distinguishing "argument not supplied" (use market default) from None
_DEFAULT: Any = object()


def _field(data: Any, key: str, default: Any = None) -> Any:
    """Return ``data[key]`` when ``data`` is a mapping, else ``default``."""
    if isinstance(data, dict):
        return cast('dict[str, Any]', data).get(key, default)
    return default


def _rows(data: Any, key: str | None = None) -> list[Any]:
    """Return a JSON array, optionally unwrapping ``data[key]`` first."""
    if key is not None:
        data = _field(data, key, data)
    return cast('list[Any]', data) if isinstance(data, list) else []


def _day_key(day: date | str) -> str:
    return day.isoformat() if isinstance(day, date) else day


class _Resource:
    def __init__(self, client: CookidooClient) -> None:
        self._c = client


# --------------------------------------------------------------------------- recipes
class RecipesResource(_Resource):
    """Recipe details, variants, ratings, and personal notes."""

    async def get(self, recipe_id: str) -> Recipe:
        """Full recipe details (ingredients, steps, nutrition, devices, assets)."""
        url = await self._c.resolve(R.RECIPE_DETAILS, 'recipe:details', id=recipe_id)
        data = await self._c.request_json('GET', url, accept=const.MEDIA_RECIPE)
        return Recipe.model_validate(data)

    async def variants(self, cluster_id: str) -> list[dict[str, Any]]:
        """Recipe variants for a cluster (e.g. TM5/TM6/TM7 renditions)."""
        url = await self._c.resolve(R.RECIPE_DETAILS, 'recipe-variants', clusterId=cluster_id)
        return await self._c.request_json('GET', url) or []

    async def collections_of(self, recipe_id: str) -> Any:
        """Managed collections that contain this recipe."""
        url = await self._c.resolve(R.RECIPE_DETAILS, 'recipe:recipe-collections', id=recipe_id)
        return await self._c.request_json('GET', url)

    async def aggregated_rating(self, recipe_id: str) -> AggregatedRating:
        url = await self._c.resolve(R.RATING, 'rating:aggregated-rating-recipe', recipeId=recipe_id)
        return AggregatedRating.model_validate(await self._c.request_json('GET', url))

    async def user_rating(self, recipe_id: str) -> Any:
        url = await self._c.resolve(R.RATING, 'rating:user-rating-recipe', recipeId=recipe_id)
        return await self._c.request_json('GET', url)

    async def set_user_rating(self, recipe_id: str, rating: int) -> Any:
        url = await self._c.resolve(R.RATING, 'rating:user-rating-recipe', recipeId=recipe_id)
        return await self._c.request_json('PUT', url, json={'rating': rating}, content_type='application/json')

    # --- personal recipe notes (feature no other SDK exposes) ---
    async def get_note(self, recipe_id: str) -> RecipeNote | None:
        url = await self._c.resolve(R.RECIPE_NOTES, 'recipe-notes:recipe-note', recipeId=recipe_id)
        data = await self._c.request_json('GET', url)
        return RecipeNote.model_validate(data) if isinstance(data, dict) else None

    async def create_note(self, recipe_id: str, text: str) -> RecipeNote:
        # verified live: body field is "text"; returns {noteId, userId, recipeId, text, modifiedAt}
        url = await self._c.resolve(R.RECIPE_NOTES, 'recipe-notes:recipe-note-create')
        data = await self._c.request_json(
            'POST', url, json={'recipeId': recipe_id, 'text': text}, content_type='application/json'
        )
        return RecipeNote.model_validate(data)

    async def update_note(self, recipe_id: str, text: str) -> RecipeNote:
        url = await self._c.resolve(R.RECIPE_NOTES, 'recipe-notes:recipe-note', recipeId=recipe_id)
        data = await self._c.request_json('PUT', url, json={'text': text}, content_type='application/json')
        return RecipeNote.model_validate(data)

    async def delete_note(self, recipe_id: str) -> None:
        url = await self._c.resolve(R.RECIPE_NOTES, 'recipe-notes:recipe-note', recipeId=recipe_id)
        await self._c.request_json('DELETE', url)


# --------------------------------------------------------------------------- search
class SearchResource(_Resource):
    """Recipe and ingredient search."""

    async def recipes(
        self,
        query: str | None = None,
        *,
        languages: str | Sequence[str] | None = _DEFAULT,
        context: str = 'recipes',
        filters: dict[str, Any] | None = None,
        limit: int | None = None,
        pagination: str | int | None = None,
        focus: str | None = None,
    ) -> SearchResult:
        """Search recipes.

        By default results are restricted to the market's content languages
        (e.g. ``es-MX,es,en`` for the ``mx`` market) — matching the app, which
        otherwise returns recipes in *every* language. Pass ``languages=None`` to
        search globally, or an explicit language list to override.

        ``filters`` is a dict of extra filter-name -> value(s) (e.g.
        ``{"categories": "...", "countries": "MX"}``), merged into the request.
        """
        merged: dict[str, Any] = dict(filters or {})
        if languages is _DEFAULT:
            if 'languages' not in merged:
                merged['languages'] = ','.join(self._c.market.content_languages)
        elif languages is not None:
            merged['languages'] = languages if isinstance(languages, str) else ','.join(languages)

        params: dict[str, Any] = {'context': context}
        if query is not None:
            params['query'] = query
        if limit is not None:
            params['limit'] = limit
        if pagination is not None:
            params['pagination'] = pagination
        if focus is not None:
            params['focus'] = focus
        if merged:
            # HAL template uses filters* (exploded) -> key=value pairs on the wire
            params['filters'] = merged
        url = await self._c.resolve(R.SEARCH, 'search:searchapi', **params)
        data = await self._c.request_json('GET', url)
        return SearchResult.model_validate(data if isinstance(data, dict) else {'data': _rows(data)})

    async def ingredients(self, query: str, *, limit: int | None = None) -> Any:
        params: dict[str, Any] = {'query': query, 'language': self._c.language}
        if limit is not None:
            params['limit'] = limit
        url = await self._c.resolve(R.SEARCH, 'search:ingredientapi', **params)
        return await self._c.request_json('GET', url)


# --------------------------------------------------------------------------- shopping list
class ShoppingResource(_Resource):
    """The shopping list (the "pantry" service)."""

    async def get_list(self) -> ShoppingList:
        url = await self._c.resolve(R.PANTRY, 'pantry:home')
        return ShoppingList.model_validate(await self._c.request_json('GET', url))

    async def add_recipes(self, recipe_ids: Sequence[str]) -> Any:
        url = await self._c.resolve(R.PANTRY, 'pantry:recipe-ingredients')
        return await self._c.request_json(
            'POST', url, json={'recipeIDs': list(recipe_ids)}, content_type='application/json'
        )

    async def add_custom_recipes(self, recipe_ids: Sequence[str]) -> Any:
        url = await self._c.resolve(R.PANTRY, 'pantry:recipe-ingredients')
        payload = {'recipeIDs': [{'id': r, 'source': 'CUSTOMER'} for r in recipe_ids]}
        return await self._c.request_json('POST', url, json=payload, content_type='application/json')

    async def remove_recipes(self, recipe_ids: Sequence[str]) -> None:
        url = await self._c.resolve(R.PANTRY, 'pantry:remove-recipe')
        await self._c.request_json('POST', url, json={'recipeIDs': list(recipe_ids)}, content_type='application/json')

    async def add_additional_items(self, names: Sequence[str]) -> list[AdditionalItem]:
        url = await self._c.resolve(R.PANTRY, 'pantry:add-additional-items-v2')
        data = await self._c.request_json(
            'POST', url, json={'itemsValue': list(names)}, content_type='application/json'
        )
        return [AdditionalItem.model_validate(r) for r in _rows(data, 'data')]

    async def edit_additional_items(self, items: Sequence[AdditionalItem | dict[str, Any]]) -> Any:
        url = await self._c.resolve(R.PANTRY, 'pantry:edit-additional-items')
        body = {'additionalItems': [_ai_id_name(i) for i in items]}
        return await self._c.request_json('POST', url, json=body, content_type='application/json')

    async def remove_additional_items(self, item_ids: Sequence[str]) -> None:
        url = await self._c.resolve(R.PANTRY, 'pantry:remove-additional-items')
        await self._c.request_json(
            'POST', url, json={'additionalItemIDs': list(item_ids)}, content_type='application/json'
        )

    async def set_ingredient_ownership(self, items: Sequence[tuple[str, bool]]) -> Any:
        """Mark ingredient items owned/unowned. ``items`` = list of (id, is_owned)."""
        url = await self._c.resolve(R.PANTRY, 'pantry:edit-ingredients-ownership')
        now = int(time.time())
        body = {'ingredients': [{'id': i, 'isOwned': o, 'ownedTimestamp': now} for i, o in items]}
        return await self._c.request_json('POST', url, json=body, content_type='application/json')

    async def set_additional_item_ownership(self, items: Sequence[tuple[str, bool]]) -> Any:
        url = await self._c.resolve(R.PANTRY, 'pantry:edit-additional-items-ownership')
        now = int(time.time())
        body = {'additionalItems': [{'id': i, 'isOwned': o, 'ownedTimestamp': now} for i, o in items]}
        return await self._c.request_json('POST', url, json=body, content_type='application/json')

    async def clear(self) -> None:
        url = await self._c.resolve(R.PANTRY, 'pantry:home')
        await self._c.request_json('DELETE', url)


def _ai_id_name(i: AdditionalItem | dict[str, Any]) -> dict[str, Any]:
    if isinstance(i, AdditionalItem):
        return {'id': i.id, 'name': i.name}
    return {'id': i['id'], 'name': i['name']}


# --------------------------------------------------------------------------- planner
class PlannerResource(_Resource):
    """The meal planner (weekly calendar)."""

    async def get_week(self, day: date | str | None = None) -> CalendarWeek:
        """Return the meal-plan week containing ``day`` (default: today)."""
        key = _day_key(day or datetime.now(tz=UTC).date())
        url = await self._c.resolve(R.PLANNING, 'planning:api-my-week-enhanced-from-date', dayKey=key)
        return CalendarWeek.model_validate(await self._c.request_json('GET', url))

    async def add_recipes(self, day: date | str, recipe_ids: Sequence[str], *, custom: bool = False) -> CalendarDay:
        url = await self._c.resolve(R.PLANNING, 'planning:api-my-day')
        body: dict[str, Any] = {'dayKey': _day_key(day), 'recipeIds': list(recipe_ids)}
        if custom:
            body['recipeSource'] = 'CUSTOMER'
        # verified live: my-day add uses PUT (not POST)
        data = await self._c.request_json(
            'PUT', url, json=body, accept=const.MEDIA_PLANNING_MY_DAY, content_type='application/json'
        )
        return CalendarDay.model_validate(_field(data, 'content', data))

    async def remove_recipe(self, day: date | str, recipe_id: str, *, custom: bool = False) -> Any:
        vars: dict[str, Any] = {'dayKey': _day_key(day), 'recipeId': recipe_id}
        vars['recipeSource'] = 'CUSTOMER' if custom else None
        url = await self._c.resolve(R.PLANNING, 'planning:api-remove-recipe', **vars)
        return await self._c.request_json('DELETE', url, accept=const.MEDIA_PLANNING_MY_DAY)


# --------------------------------------------------------------------------- collections
class CollectionsResource(_Resource):
    """Custom lists, bookmarks, and shared collections (the "organize" service)."""

    async def custom_lists(self, page: int = 0) -> list[Collection]:
        url = await self._c.resolve(R.ORGANIZE, 'organize:api-custom-list', page=page)
        data = await self._c.request_json('GET', url, accept=const.MEDIA_CUSTOM_LIST)
        return [Collection.model_validate(c) for c in _rows(data, 'customlists')]

    async def create_custom_list(self, title: str) -> Collection:
        url = await self._c.resolve(R.ORGANIZE, 'organize:api-custom-list')
        data = await self._c.request_json(
            'POST',
            url,
            json={'title': title},
            accept=const.MEDIA_CUSTOM_LIST,
            content_type='application/json',
        )
        return Collection.model_validate(_field(data, 'content', data))

    async def add_recipes_to_list(self, list_id: str, recipe_ids: Sequence[str]) -> Collection:
        # verified: add-recipes-to-custom-list uses PUT with CustomListRequestDto
        url = await self._c.resolve(R.ORGANIZE, 'organize:api-custom-list') + f'/{list_id}'
        data = await self._c.request_json(
            'PUT',
            url,
            json={'customlistId': list_id, 'recipeIds': list(recipe_ids)},
            accept=const.MEDIA_CUSTOM_LIST,
            content_type='application/json',
        )
        return Collection.model_validate(_field(data, 'content', data))

    async def delete_custom_list(self, list_id: str) -> None:
        url = await self._c.resolve(R.ORGANIZE, 'organize:api-custom-list') + f'/{list_id}'
        await self._c.request_json('DELETE', url, accept=const.MEDIA_CUSTOM_LIST)

    async def bookmarks(self) -> Any:
        url = await self._c.resolve(R.ORGANIZE, 'organize:api-bookmark')
        return await self._c.request_json('GET', url, accept=const.MEDIA_BOOKMARK)

    async def add_bookmark(self, recipe_id: str) -> Any:
        """Bookmark (save) a recipe — PUT {recipeId}."""
        url = await self._c.resolve(R.ORGANIZE, 'organize:api-bookmark')
        return await self._c.request_json(
            'PUT',
            url,
            json={'recipeId': recipe_id},
            accept=const.MEDIA_BOOKMARK,
            content_type='application/json',
        )

    async def get_by_code(self, code: str) -> Collection:
        url = await self._c.resolve(R.COLLECTIONS, 'collection:collection-details', code=code)
        return Collection.model_validate(await self._c.request_json('GET', url))


# --------------------------------------------------------------------------- custom recipes
class CustomRecipesResource(_Resource):
    """User-created ("customer") recipes."""

    async def list(self) -> list[CustomRecipe]:
        url = await self._c.resolve(R.CUSTOMER_RECIPES, 'customer-recipes:recipes-list')
        data = await self._c.request_json('GET', url, accept=const.MEDIA_CUSTOMER_RECIPE_FULL)
        return [CustomRecipe.model_validate(i) for i in _rows(data, 'items')]

    async def get(self, recipe_id: str) -> CustomRecipe:
        url = await self._c.resolve(R.CUSTOMER_RECIPES, 'customer-recipes:recipe-details', id=recipe_id)
        return CustomRecipe.model_validate(
            await self._c.request_json('GET', url, accept=const.MEDIA_CUSTOMER_RECIPE_FULL)
        )

    async def create(self, name: str) -> CustomRecipe:
        url = await self._c.resolve(R.CUSTOMER_RECIPES, 'customer-recipes:recipe-create')
        data = await self._c.request_json('POST', url, json={'recipeName': name}, content_type='application/json')
        return CustomRecipe.model_validate(data)

    async def delete(self, recipe_id: str) -> None:
        url = await self._c.resolve(R.CUSTOMER_RECIPES, 'customer-recipes:recipe-details', id=recipe_id)
        await self._c.request_json('DELETE', url)


# --------------------------------------------------------------------------- recommendations
class RecommendationsResource(_Resource):
    """Personalized recommendations (For You feed, similar recipes)."""

    async def for_you(self) -> ForYouFeed:
        url = await self._c.resolve(R.RECOMMENDER, 'recommender:mobile_foryou')
        return ForYouFeed.model_validate(await self._c.request_json('GET', url))

    async def similar(self, recipe_id: str) -> list[RecipeSummary]:
        url = await self._c.resolve(R.RECOMMENDER, 'recommender:mobile_simrec', recipeid=recipe_id)
        data = await self._c.request_json('GET', url)
        return [RecipeSummary.model_validate(r) for r in _rows(data, 'data')]


# --------------------------------------------------------------------------- profile / account
class ProfileResource(_Resource):
    """User profile, community profile, and subscriptions."""

    async def community_profile(self) -> CommunityProfile:
        url = await self._c.resolve(R.COMMUNITY_PROFILE, 'community-profile:user-private-profile')
        return CommunityProfile.model_validate(await self._c.request_json('GET', url))

    async def subscriptions(self) -> list[Subscription]:
        url = await self._c.resolve(R.OWNERSHIP, 'ownership:subscriptionsV2')
        data = await self._c.request_json('GET', url)
        return [Subscription.model_validate(s) for s in _rows(data)]

    async def active_subscription(self) -> Subscription | None:
        for s in await self.subscriptions():
            if s.active:
                return s
        return None

    async def saved_searches(self) -> Any:
        url = await self._c.resolve(R.COMMUNITY_PROFILE, 'community-profile:saved-searches')
        return await self._c.request_json('GET', url)

    async def me(self):
        """Decoded id_token claims (email, name, country, roles)."""
        return await self._c.get_user_info()


# --------------------------------------------------------------------------- devices / monitoring
class DevicesResource(_Resource):
    """Registered Thermomix devices, accessories, and remote monitoring (RMI)."""

    async def thermomix_versions(self) -> list[str]:
        url = await self._c.resolve(R.CUSTOMER_DEVICES, 'customer-devices:thermomix-versions')
        return _rows(await self._c.request_json('GET', url))

    async def accessory_ids(self) -> list[str]:
        url = await self._c.resolve(R.CUSTOMER_DEVICES, 'customer-devices:api-accessory-ids')
        return _rows(await self._c.request_json('GET', url))

    async def monitored_devices(self, nonce: str | None = None) -> Any:
        """Devices currently reachable for remote monitoring (IoT gateway)."""
        url = await self._c.resolve(R.RMI_CONFIG, 'rmi:devices', nonce=nonce or str(int(time.time())))
        return await self._c.request_json('GET', url, headers={'rmi-api-version': const.RMI_API_VERSION})

    async def register_push_token(self, token: str, mobile_app_id: str) -> Any:
        """Register an FCM push token so the IoT gateway pushes cooking status to it."""
        url = await self._c.resolve(R.RMI_CONFIG, 'rmi:register-token')
        body = {'token': token, 'bundleId': const.ANDROID_PACKAGE, 'platform': 'AN', 'mobileAppId': mobile_app_id}
        return await self._c.request_json(
            'POST', url, json=body, content_type='application/json', headers={'rmi-api-version': const.RMI_API_VERSION}
        )

    async def unregister_push_token(self, token: str) -> None:
        """Stop the IoT gateway pushing to a previously-registered FCM token."""
        url = await self._c.resolve(R.RMI_CONFIG, 'rmi:unregister')
        await self._c.request_json(
            'POST',
            url,
            json={'entries': [{'token': token}]},
            content_type='application/json',
            headers={'rmi-api-version': const.RMI_API_VERSION},
        )

    async def watch_cooking(
        self,
        *,
        credentials_path: str | Path | None = None,
        mobile_app_id: str | None = None,
    ) -> AsyncGenerator[CookingStatus]:
        """Yield live :class:`CookingStatus` frames from a connected Thermomix.

        Registers as a Firebase Cloud Messaging client (using the app's Firebase
        project), registers that token with Cookidoo's IoT gateway, then streams
        each status push. Requires the ``monitor`` extra (``firebase-messaging``).

        Parameters
        ----------
        credentials_path
            Where to persist FCM device credentials so the push token stays stable
            across runs. If omitted, an ephemeral registration is used.
        mobile_app_id
            A stable per-install id sent to the gateway; a random one is generated
            if omitted.

        Yields:
            CookingStatus frames as they are pushed (state, step, time remaining…).
        """
        try:
            from firebase_messaging import FcmPushClient, FcmRegisterConfig
        except ModuleNotFoundError as exc:  # pragma: no cover
            raise CookidooError("Cooking monitor needs the 'monitor' extra: pip install 'cookidoo[monitor]'") from exc

        creds: dict[str, Any] | None = None
        creds_file = Path(credentials_path) if credentials_path else None
        if creds_file and creds_file.exists():
            creds = json.loads(creds_file.read_text())

        def save_creds(updated: dict[str, Any]) -> None:
            if creds_file:
                creds_file.parent.mkdir(parents=True, exist_ok=True)
                creds_file.write_text(json.dumps(updated))

        app_id = mobile_app_id or str(uuid.uuid4())
        config = FcmRegisterConfig(
            project_id=const.FIREBASE_PROJECT_ID,
            app_id=const.FIREBASE_APP_ID,
            api_key=const.FIREBASE_API_KEY,
            messaging_sender_id=const.FIREBASE_SENDER_ID,
            bundle_id=const.ANDROID_PACKAGE,
        )
        queue: asyncio.Queue[CookingStatus] = asyncio.Queue()

        def on_push(notification: dict[str, Any], _persistent_id: str, _ctx: object) -> None:
            payload: Any = notification.get('data', notification)
            queue.put_nowait(CookingStatus.model_validate(payload))

        client = FcmPushClient(on_push, config, creds, save_creds)
        fcm_token = await client.checkin_or_register()
        await self.register_push_token(fcm_token, app_id)
        await client.start()
        try:
            while True:
                yield await queue.get()
        finally:
            await self.unregister_push_token(fcm_token)
            await client.stop()


# --------------------------------------------------------------------------- assistant (copilot)
class AssistantResource(_Resource):
    """Cookidoo AI assistant ("copilot").

    Note: in the app the *chat* itself is a hosted **WebView**, not a JSON REST
    endpoint — there is no request DTO to POST. Use :meth:`chat_url` to obtain the
    authenticated web URL. The tips/tutorial content is a normal GET.
    """

    async def chat_url(self) -> str:
        """Return the assistant chat WebView URL (open in a browser/WebView)."""
        return await self._c.resolve(R.COPILOT, 'assistant:chat')

    async def tips(self) -> Any:
        url = await self._c.resolve(R.COPILOT, 'assistant:tips-and-tricks')
        return await self._c.request_json('GET', url)


# --------------------------------------------------------------------------- notifications
class NotificationsResource(_Resource):
    """The mobile notification center."""

    async def list(self) -> Any:
        url = await self._c.resolve(R.NOTIFICATION_CENTER, 'mobile:notifications')
        return await self._c.request_json('GET', url)


# --------------------------------------------------------------------------- app config
class ConfigResource(_Resource):
    """Remote mobile app configuration and feature toggles."""

    async def mobile_config(self) -> Any:
        url = await self._c.resolve(R.MOBILE_CONFIG, 'mobile-config:config')
        return await self._c.request_json('GET', url)

    async def feature_toggles(self) -> dict[str, Any]:
        cfg = await self.mobile_config()
        out: dict[str, Any] = {}
        for t in _rows(cfg, 'featureToggles'):
            out[_field(t, 'feature')] = _field(t, 'configuration')
        return out
