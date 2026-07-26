"""Exceptions raised by the Cookidoo SDK."""

from __future__ import annotations


class CookidooError(Exception):
    """Base class for all Cookidoo SDK errors."""


class CookidooConfigError(CookidooError):
    """Invalid configuration (e.g. unknown market, missing credentials)."""


class CookidooAuthError(CookidooError):
    """Authentication or token refresh failed (invalid credentials or expired session)."""


class CookidooRequestError(CookidooError):
    """A network request failed (timeout, connection error, unexpected status)."""

    def __init__(self, message: str, *, status: int | None = None, body: str | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.body = body


class CookidooParseError(CookidooError):
    """A response body could not be parsed into the expected shape."""


class CookidooLinkError(CookidooError):
    """A required HAL link relation was not present in the home document."""

    def __init__(self, rel: str) -> None:
        super().__init__(
            f'API link relation {rel!r} is not available for this account/market. '
            'It may require a different subscription tier or be unsupported in your region.'
        )
        self.rel = rel
