"""Unofficial comprehensive async Python SDK for the Cookidoo (Thermomix) mobile API."""

from . import models
from .auth import Token, UserInfo
from .client import CookidooClient
from .exceptions import (
    CookidooAuthError,
    CookidooConfigError,
    CookidooError,
    CookidooLinkError,
    CookidooParseError,
    CookidooRequestError,
)
from .localization import Market, all_markets, get_market

__all__ = [
    'CookidooAuthError',
    'CookidooClient',
    'CookidooConfigError',
    'CookidooError',
    'CookidooLinkError',
    'CookidooParseError',
    'CookidooRequestError',
    'Market',
    'Token',
    'UserInfo',
    'all_markets',
    'get_market',
    'models',
]

__version__ = '0.1.0'
