"""The core Cookidoo async client: auth, HAL navigation, request plumbing."""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar, cast

import httpx

from . import const
from .auth import Authenticator, Token
from .exceptions import (
    CookidooAuthError,
    CookidooParseError,
    CookidooRequestError,
)
from .hal import Link, parse_links, require_link
from .localization import Market, get_market

if TYPE_CHECKING:
    from .resources import (
        AssistantResource,
        CollectionsResource,
        ConfigResource,
        CustomRecipesResource,
        DevicesResource,
        NotificationsResource,
        PlannerResource,
        ProfileResource,
        RecipesResource,
        RecommendationsResource,
        SearchResource,
        ShoppingResource,
    )

_LOGGER = logging.getLogger("cookidoo")

_R = TypeVar("_R")


class CookidooClient:
    """Async client for the Cookidoo mobile API.

    Usage::

        async with CookidooClient(email, password, market="mx") as cc:
            await cc.login()
            me = await cc.get_user_info()
            results = await cc.search.recipes("pasta")
    """

    def __init__(
        self,
        email: str,
        password: str,
        market: str = "xp",
        *,
        language: str | None = None,
        environment: str = "prod",
        token: Token | None = None,
        http: httpx.AsyncClient | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._market: Market = get_market(market)
        self._email = email
        self._password = password
        self._environment = environment
        self._language = self._market.language_for(language)
        self._token = token

        self._base_url = const.ENV_HOST_TEMPLATES[environment].format(market=self._market.market_code.lower())
        self._auth = Authenticator(email, password, self._market.market_code, ui_locale=self._language)
        self._timeout = timeout
        self._owns_http = http is None
        self._http = http or httpx.AsyncClient(
            timeout=timeout,
            headers={
                "User-Agent": const.USER_AGENT,
                "Accept-Language": self._language,
            },
        )

        # HAL document caches
        self._root_links: dict[str, Link] | None = None
        self._subdoc_links: dict[str, dict[str, Link]] = {}
        self._oidc: tuple[str, str] | None = None  # (authorize, token) endpoints

        # lazily-attached resource namespaces
        self._resources: dict[str, Any] = {}

    # ------------------------------------------------------------------ lifecycle

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_http:
            await self._http.aclose()

    @property
    def market(self) -> Market:
        return self._market

    @property
    def language(self) -> str:
        return self._language

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def token(self) -> Token | None:
        return self._token

    # ------------------------------------------------------------------ HAL core

    async def root_links(self) -> dict[str, Link]:
        """Fetch (and cache) the root ``/.well-known/mobile-home`` link map."""
        if self._root_links is None:
            url = self._base_url + const.HOME_DOCUMENT_PATH
            doc = await self._request("GET", url, accept=const.HOME_ACCEPT, authenticated=False)
            self._root_links = parse_links(doc)
        return self._root_links

    async def subdoc_links(
        self, root_rel: str, *, accept: str | None = None, authenticated: bool = True
    ) -> dict[str, Link]:
        """Follow a root relation to its sub-home-document and cache its links."""
        if root_rel not in self._subdoc_links:
            link = require_link(await self.root_links(), root_rel)
            doc = await self._request(
                "GET",
                link.expand(lang=self._language),
                accept=accept or const.HOME_ACCEPT,
                authenticated=authenticated,
            )
            self._subdoc_links[root_rel] = parse_links(doc)
        return self._subdoc_links[root_rel]

    async def resolve(
        self,
        root_rel: str,
        sub_rel: str | None = None,
        *,
        accept: str | None = None,
        authenticated: bool = True,
        **vars: Any,
    ) -> str:
        """Resolve an absolute URL from a (root rel [, sub rel]) HAL path.

        ``vars`` are used to expand URI templates; ``lang`` defaults to the
        configured language.
        """
        vars.setdefault("lang", self._language)
        if sub_rel is None:
            link = require_link(await self.root_links(), root_rel)
        else:
            link = require_link(
                await self.subdoc_links(root_rel, accept=accept, authenticated=authenticated),
                sub_rel,
            )
        return link.expand(**vars)

    async def oidc_endpoints(self) -> tuple[str, str]:
        """Discover the ``(authorization_endpoint, token_endpoint)`` via HAL."""
        if self._oidc is None:
            disc_url = await self.resolve(
                const.Rel.AUTH,
                const.AUTH_REL_DISCOVERY,
                accept=const.HOME_ACCEPT,
                authenticated=False,
            )
            doc = await self._request("GET", disc_url, authenticated=False)
            try:
                self._oidc = (doc["authorization_endpoint"], doc["token_endpoint"])
            except (KeyError, TypeError) as e:
                raise CookidooParseError("OpenID discovery document malformed") from e
        return self._oidc

    # ------------------------------------------------------------------ auth

    async def login(self) -> Token:
        """Authenticate and store a token. Auto-corrects the market if needed."""
        authorize, token_url = await self.oidc_endpoints()
        # Run the OAuth "browser" dance (authorize -> login -> callback) on an
        # isolated client with its own cookie jar. Reusing a shared client (e.g.
        # Home Assistant's) would let a leftover CIAM session cookie make /authorize
        # skip the login page and redirect straight to the custom-scheme callback,
        # which httpx cannot follow. Only the resulting bearer token is needed for
        # the actual API calls (made on self._http).
        async with httpx.AsyncClient(
            timeout=self._timeout,
            headers={
                "User-Agent": const.USER_AGENT,
                "Accept-Language": self._language,
            },
        ) as auth_http:
            self._token = await self._auth.login(auth_http, authorize, token_url)
        _LOGGER.info("Logged in as %s", self._token.user.email if self._token.user else "?")
        return self._token

    async def ensure_token(self) -> Token:
        """Return a valid token, refreshing or re-logging in as needed."""
        if self._token is None:
            return await self.login()
        if self._token.expired:
            if self._token.refresh_token:
                try:
                    _, token_url = await self.oidc_endpoints()
                    self._token = await self._auth.refresh(self._http, token_url, self._token.refresh_token)
                    return self._token
                except CookidooAuthError:
                    _LOGGER.info("Refresh failed, re-authenticating")
            return await self.login()
        return self._token

    async def get_user_info(self):
        """Return the decoded id_token user info (no network call after login)."""
        token = await self.ensure_token()
        return token.user

    # ------------------------------------------------------------------ requests

    async def request_json(
        self,
        method: str,
        url: str,
        *,
        json: Any | None = None,
        params: Mapping[str, Any] | None = None,
        accept: str | None = None,
        content_type: str | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        """Authenticated JSON request helper used by resource classes."""
        return await self._request(
            method,
            url,
            json=json,
            params=params,
            accept=accept,
            content_type=content_type,
            headers=headers,
            authenticated=True,
        )

    async def _request(
        self,
        method: str,
        url: str,
        *,
        json: Any | None = None,
        params: Mapping[str, Any] | None = None,
        accept: str | None = None,
        content_type: str | None = None,
        headers: Mapping[str, str] | None = None,
        authenticated: bool = True,
        _retry: bool = True,
    ) -> Any:
        # App headers are applied per-request (not only on an owned client) so a
        # caller-supplied shared client (e.g. Home Assistant's) still sends them.
        hdrs: dict[str, str] = {
            "Accept": accept or "application/json",
            "User-Agent": const.USER_AGENT,
            "Accept-Language": self._language,
        }
        if content_type:
            hdrs["Content-Type"] = content_type
        if headers:
            hdrs.update(headers)
        if authenticated:
            token = await self.ensure_token()
            hdrs["Authorization"] = f"Bearer {token.access_token}"

        try:
            resp = await self._http.request(method, url, json=json, params=params, headers=hdrs, follow_redirects=True)
        except httpx.TimeoutException as e:
            raise CookidooRequestError(f"{method} {url} timed out") from e
        except httpx.HTTPError as e:
            raise CookidooRequestError(f"{method} {url} failed: {e}") from e

        if resp.status_code == 401 and authenticated and _retry:
            # token may have just expired server-side; force refresh once
            self._token = None
            return await self._request(
                method,
                url,
                json=json,
                params=params,
                accept=accept,
                content_type=content_type,
                headers=headers,
                authenticated=authenticated,
                _retry=False,
            )
        if resp.status_code == 401:
            raise CookidooAuthError(f"Unauthorized: {method} {url}")
        if resp.status_code == 204 or not resp.content:
            return None
        if not resp.is_success:
            raise CookidooRequestError(
                f"{method} {url} -> {resp.status_code}",
                status=resp.status_code,
                body=resp.text[:500],
            )
        ctype = resp.headers.get("content-type", "")
        if "json" not in ctype and "hal" not in ctype:
            return resp.text
        try:
            return resp.json()
        except ValueError as e:
            raise CookidooParseError(f"Invalid JSON from {url}") from e

    # ------------------------------------------------------------------ resources

    def _resource(self, name: str, factory: Callable[[CookidooClient], _R]) -> _R:
        cached = self._resources.get(name)
        if cached is None:
            cached = factory(self)
            self._resources[name] = cached
        return cast("_R", cached)

    @property
    def recipes(self) -> RecipesResource:
        """Recipe details, variants, ratings, and personal notes."""
        from .resources import RecipesResource

        return self._resource("recipes", RecipesResource)

    @property
    def search(self) -> SearchResource:
        """Recipe and ingredient search."""
        from .resources import SearchResource

        return self._resource("search", SearchResource)

    @property
    def shopping(self) -> ShoppingResource:
        """The shopping list (the "pantry" service)."""
        from .resources import ShoppingResource

        return self._resource("shopping", ShoppingResource)

    @property
    def planner(self) -> PlannerResource:
        """The meal planner (weekly calendar)."""
        from .resources import PlannerResource

        return self._resource("planner", PlannerResource)

    @property
    def collections(self) -> CollectionsResource:
        """Custom lists, bookmarks, and shared collections."""
        from .resources import CollectionsResource

        return self._resource("collections", CollectionsResource)

    @property
    def custom_recipes(self) -> CustomRecipesResource:
        """User-created ("customer") recipes."""
        from .resources import CustomRecipesResource

        return self._resource("custom_recipes", CustomRecipesResource)

    @property
    def recommendations(self) -> RecommendationsResource:
        """Personalized recommendations (For You feed, similar recipes)."""
        from .resources import RecommendationsResource

        return self._resource("recommendations", RecommendationsResource)

    @property
    def profile(self) -> ProfileResource:
        """User profile, community profile, and subscriptions."""
        from .resources import ProfileResource

        return self._resource("profile", ProfileResource)

    @property
    def devices(self) -> DevicesResource:
        """Registered Thermomix devices, accessories, and remote monitoring."""
        from .resources import DevicesResource

        return self._resource("devices", DevicesResource)

    @property
    def assistant(self) -> AssistantResource:
        """Cookidoo AI assistant (copilot)."""
        from .resources import AssistantResource

        return self._resource("assistant", AssistantResource)

    @property
    def notifications(self) -> NotificationsResource:
        """The mobile notification center."""
        from .resources import NotificationsResource

        return self._resource("notifications", NotificationsResource)

    @property
    def config(self) -> ConfigResource:
        """Remote mobile app configuration and feature toggles."""
        from .resources import ConfigResource

        return self._resource("config", ConfigResource)
