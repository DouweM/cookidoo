"""Headless PKCE OAuth2 login against Cookidoo's CIAM identity provider.

Replicates the Android app's WebView code-grant flow without a browser:
authorize -> CIAM login page -> submit credentials -> capture the
``com.vorwerk.cookidoo://code-grant?code=...`` redirect -> exchange the code
(with PKCE verifier) for a bearer token at the discovered ``token_endpoint``.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Self, cast
from urllib.parse import parse_qs, urlsplit

import httpx

from . import const
from .exceptions import CookidooAuthError, CookidooParseError

_REDIRECT_SCHEME = 'com.vorwerk.cookidoo://'
_REQUEST_ID_RE = re.compile(
    r'name=["\']requestId["\'][^>]*value=["\']([^"\']+)["\']'
    r'|value=["\']([0-9a-fA-F-]{16,})["\'][^>]*name=["\']requestId["\']'
)
_FORM_ACTION_RE = re.compile(r'<form[^>]*action=["\']([^"\']+)["\']', re.IGNORECASE)


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('ascii')


def generate_pkce() -> tuple[str, str]:
    """Return ``(verifier, challenge)`` for PKCE S256."""
    verifier = _b64url(os.urandom(64))
    challenge = _b64url(hashlib.sha256(verifier.encode('ascii')).digest())
    return verifier, challenge


@dataclass
class UserInfo:
    """Claims decoded from the ``id_token`` JWT (no network call)."""

    email: str | None = None
    given_name: str | None = None
    family_name: str | None = None
    dcid: str | None = None  # `sub`
    roles: tuple[str, ...] = ()
    country_of_residence: str | None = None


@dataclass
class Token:
    """An OAuth token set plus derived expiry and decoded user info."""

    access_token: str
    refresh_token: str | None
    token_type: str
    id_token: str | None
    expires_at: float  # epoch seconds
    user: UserInfo | None = None

    @property
    def expired(self) -> bool:
        return time.time() >= self.expires_at - 60  # refresh 60s early

    @classmethod
    def from_response(cls, data: dict[str, Any]) -> Self:
        """Build a token from an OAuth token-endpoint response."""
        try:
            expires_in = int(data.get('expires_in', 3600))
            id_token = data.get('id_token')
            return cls(
                access_token=data['access_token'],
                refresh_token=data.get('refresh_token'),
                token_type=data.get('token_type', 'Bearer'),
                id_token=id_token,
                expires_at=time.time() + expires_in,
                user=decode_id_token(id_token) if id_token else None,
            )
        except KeyError as e:
            raise CookidooParseError(f'Token response missing field: {e}') from e


def decode_id_token(id_token: str) -> UserInfo | None:
    """Decode the JWT payload (segment 1) into :class:`UserInfo`. No signature check."""
    try:
        payload_b64 = id_token.split('.')[1]
        payload_b64 += '=' * (-len(payload_b64) % 4)
        decoded = json.loads(base64.urlsafe_b64decode(payload_b64))
    except (IndexError, ValueError, json.JSONDecodeError):
        return None
    if not isinstance(decoded, dict):
        return None
    payload = cast('dict[str, Any]', decoded)
    custom = payload.get('customFields')
    custom = cast('dict[str, Any]', custom) if isinstance(custom, dict) else {}
    roles = payload.get('roles')
    roles = cast('list[Any]', roles) if isinstance(roles, list) else []
    return UserInfo(
        email=payload.get('email'),
        given_name=payload.get('given_name'),
        family_name=payload.get('family_name'),
        dcid=payload.get('sub'),
        roles=tuple(str(r) for r in roles),
        country_of_residence=custom.get('country_of_residence'),
    )


def _basic_auth_header() -> str:
    raw = f'{const.OAUTH_TOKEN_BASIC_USER}:{const.OAUTH_TOKEN_BASIC_PASS}'.encode()
    return 'Basic ' + base64.b64encode(raw).decode('ascii')


def _code_from_redirect(location: str) -> str | None:
    """Extract the ``code`` param from a ``code-grant`` redirect URL.

    Raises :class:`CookidooAuthError` if the redirect carries an OAuth ``error``.
    """
    query = parse_qs(urlsplit(location).query)
    if 'error' in query:
        desc = query.get('error_description', [''])
        raise CookidooAuthError(f'Authorization failed: {query["error"][0]} {desc[0]}')
    codes = query.get('code')
    return codes[0] if codes else None


async def _follow_to_code(http: httpx.AsyncClient, response: httpx.Response, *, max_hops: int = 12) -> str | None:
    """Follow a redirect chain manually until the custom-scheme code-grant URL.

    Returns the authorization ``code`` if found, else ``None``.
    """
    for _ in range(max_hops):
        location = response.headers.get('location')
        if location is None:
            return None
        if location.startswith(_REDIRECT_SCHEME):
            return _code_from_redirect(location)
        # resolve relative locations against the current URL
        next_url = str(httpx.URL(response.url).join(location))
        response = await http.get(next_url, follow_redirects=False)
    return None


class Authenticator:
    """Performs and refreshes CIAM PKCE logins for a single account/market."""

    def __init__(
        self,
        email: str,
        password: str,
        market: str,
        *,
        ui_locale: str = 'en-US',
    ) -> None:
        self._email = email
        self._password = password
        self._market = market
        self._ui_locale = ui_locale

    async def login(self, http: httpx.AsyncClient, authorization_endpoint: str, token_endpoint: str) -> Token:
        """Run the full code-grant flow and return a :class:`Token`."""
        verifier, challenge = generate_pkce()
        state = _b64url(os.urandom(16))

        authorize_params = {
            'response_type': const.OAUTH_RESPONSE_TYPE,
            'client_id': const.OAUTH_CLIENT_ID,
            'redirect_uri': const.OAUTH_REDIRECT_URI,
            'market': self._market,
            'scope': const.OAUTH_SCOPE,
            'state': state,
            'code_challenge': challenge,
            'code_challenge_method': const.OAUTH_CODE_CHALLENGE_METHOD,
            'ui_locales': self._ui_locale,
        }

        # 1. GET authorize -> follow redirects to the CIAM login page.
        resp = await http.get(authorization_endpoint, params=authorize_params, follow_redirects=True)
        if resp.status_code != 200:
            raise CookidooAuthError(f'Could not reach login page (status {resp.status_code}).')
        login_html = resp.text
        login_url = str(resp.url)

        # 2. Extract requestId + form action from the login page.
        m = _REQUEST_ID_RE.search(login_html)
        if not m:
            raise CookidooAuthError(
                'Could not locate requestId on the CIAM login page (login page layout may have changed).'
            )
        request_id = m.group(1) or m.group(2)
        action_m = _FORM_ACTION_RE.search(login_html)
        action = action_m.group(1) if action_m else '/login-srv/login'
        login_post_url = str(httpx.URL(login_url).join(action))

        # 3. POST credentials; do NOT auto-follow (custom scheme breaks httpx).
        post = await http.post(
            login_post_url,
            data={
                'requestId': request_id,
                'username': self._email,
                'password': self._password,
            },
            follow_redirects=False,
        )
        code: str | None = None
        if post.is_redirect:
            code = await _follow_to_code(http, post)
        elif post.status_code == 200:
            # Some CIAM variants return an auto-submit HTML form; try harder.
            loc = _extract_meta_or_form_redirect(post.text)
            if loc and loc.startswith(_REDIRECT_SCHEME):
                code = _code_from_redirect(loc)
        if not code:
            raise CookidooAuthError('Login did not yield an authorization code — check email/password.')

        # 4. Exchange code for tokens.
        return await self._exchange(http, token_endpoint, code=code, verifier=verifier)

    async def _exchange(self, http: httpx.AsyncClient, token_endpoint: str, *, code: str, verifier: str) -> Token:
        resp = await http.post(
            token_endpoint,
            data={
                'code': code,
                'grant_type': 'authorization_code',
                'redirect_uri': const.OAUTH_REDIRECT_URI,
                'code_verifier': verifier,
            },
            headers={
                'Authorization': _basic_auth_header(),
                'Content-Type': 'application/x-www-form-urlencoded',
                'Cookie': const.OAUTH_TOKEN_COOKIE,
            },
            follow_redirects=False,
        )
        if resp.status_code != 200:
            raise CookidooAuthError(f'Token exchange failed (status {resp.status_code}): {resp.text[:300]}')
        return Token.from_response(resp.json())

    async def refresh(self, http: httpx.AsyncClient, token_endpoint: str, refresh_token: str) -> Token:
        """Refresh an access token using the stored refresh token."""
        resp = await http.post(
            token_endpoint,
            data={'grant_type': 'refresh_token', 'refresh_token': refresh_token},
            headers={
                'Authorization': _basic_auth_header(),
                'Content-Type': 'application/x-www-form-urlencoded',
                'Cookie': const.OAUTH_TOKEN_COOKIE,
            },
            follow_redirects=False,
        )
        if resp.status_code != 200:
            raise CookidooAuthError(f'Token refresh failed (status {resp.status_code}). Re-login required.')
        data = resp.json()
        # some providers omit refresh_token on refresh; keep the old one
        data.setdefault('refresh_token', refresh_token)
        return Token.from_response(data)


def _extract_meta_or_form_redirect(html: str) -> str | None:
    m = re.search(
        r'<meta[^>]*http-equiv=["\']refresh["\'][^>]*content=["\'][^"\']*url=([^"\']+)',
        html,
        re.IGNORECASE,
    )
    if m:
        return m.group(1)
    m = _FORM_ACTION_RE.search(html)
    return m.group(1) if m else None
