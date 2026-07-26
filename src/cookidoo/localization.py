"""Market / locale resolution.

Data is loaded from ``localization_config.json``, extracted verbatim from the
Cookidoo Android app (``res/raw/localization_config.json``, v26.6.19). It is the
authoritative mapping of market code -> host + supported UI languages.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from importlib import resources

from .exceptions import CookidooConfigError


@dataclass(frozen=True)
class Market:
    """A Cookidoo market (country/region) and its API host + languages."""

    name: str
    market_code: str  # e.g. "de", "gb", "us", "xp"
    main_domain: str  # e.g. "cookidoo.de" -> API host
    main_country: str  # ISO country, e.g. "DE"
    default_language: str  # e.g. "de-DE"
    allowed_languages: tuple[str, ...] = field(default_factory=tuple)
    content_languages: tuple[str, ...] = field(default_factory=tuple)  # editorial content langs
    country_codes: tuple[str, ...] = field(default_factory=tuple)
    geo_region: str = ''
    currencies: tuple[str, ...] = field(default_factory=tuple)

    @property
    def base_url(self) -> str:
        """Base API/site URL for this market, e.g. ``https://cookidoo.de``."""
        return f'https://{self.main_domain}'

    def language_for(self, language: str | None) -> str:
        """Return a supported UI language, defaulting to the market default."""
        if language is None:
            return self.default_language
        # exact match
        if language in self.allowed_languages:
            return language
        # match on the primary subtag (e.g. "de" -> "de-CH")
        primary = language.split('-')[0].lower()
        for allowed in self.allowed_languages:
            if allowed.split('-')[0].lower() == primary:
                return allowed
        return self.default_language


@lru_cache(maxsize=1)
def _load() -> dict[str, Market]:
    raw = resources.files('cookidoo').joinpath('localization_config.json').read_text(encoding='utf-8')
    data = json.loads(raw)
    markets: dict[str, Market] = {}
    for m in data['markets']:
        # editorialContentLanguageTags is a list of comma-joined strings,
        # e.g. ["es-MX, es, en"] -> ("es-MX", "es", "en")
        content: list[str] = []
        for entry in m.get('editorialContentLanguageTags', []):
            for tag in str(entry).split(','):
                tag = tag.strip()
                if tag and tag not in content:
                    content.append(tag)
        market = Market(
            name=m['name'],
            market_code=m['marketCode'],
            main_domain=m['mainDomain'],
            main_country=m.get('mainCountry', ''),
            default_language=m['defaultUILanguage'],
            allowed_languages=tuple(m.get('allowedUILanguages', [])),
            content_languages=tuple(content),
            country_codes=tuple(m.get('countryCodes', [])),
            geo_region=m.get('geoRegion', ''),
            currencies=tuple(m.get('currencies', [])),
        )
        markets[market.market_code.lower()] = market
    return markets


def all_markets() -> list[Market]:
    """Return all known markets."""
    return list(_load().values())


def get_market(market_code: str) -> Market:
    """Resolve a market by its code (e.g. ``"de"``, ``"gb"``, ``"us"``, ``"xp"``).

    Also accepts a few convenience aliases (ISO country codes and hosts).
    """
    if not market_code:
        raise CookidooConfigError('market_code must be provided')
    key = market_code.strip().lower()
    markets = _load()
    if key in markets:
        return markets[key]
    # alias: full host (cookidoo.de)
    for m in markets.values():
        if key == m.main_domain.lower():
            return m
    # alias: ISO country code (DE -> de market's country)
    for m in markets.values():
        if key.upper() in m.country_codes:
            return m
    raise CookidooConfigError(f'Unknown market {market_code!r}. Known markets: ' + ', '.join(sorted(markets)) + '.')
