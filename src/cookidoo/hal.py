"""HAL hypermedia support: link relations + RFC 6570 URI template expansion.

The Cookidoo mobile API is HAL-based. Responses carry a ``_links`` object mapping
relation names (namespaced, e.g. ``tmde2:search``, ``pantry:home``) to link
objects ``{"href": "...", "templated": true|false}``. Templated hrefs are RFC 6570
URI templates that must be expanded with runtime variables.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast
from urllib.parse import quote

from .exceptions import CookidooLinkError, CookidooParseError

_UNRESERVED = '-._~'  # kept unencoded in addition to alnum


@dataclass(frozen=True)
class Link:
    """A HAL link."""

    href: str
    templated: bool = False

    def expand(self, **vars: Any) -> str:
        """Expand the (possibly templated) href with the given variables."""
        if not self.templated:
            return self.href
        return expand_uri_template(self.href, vars)


def parse_links(obj: Mapping[str, Any]) -> dict[str, Link]:
    """Parse the ``_links`` object of a HAL document into ``{rel: Link}``."""
    raw = obj.get('_links', obj)
    if not isinstance(raw, Mapping):
        raise CookidooParseError("Document has no valid '_links' object")
    links_obj = cast('Mapping[str, Any]', raw)
    result: dict[str, Link] = {}
    for rel, val in links_obj.items():
        if isinstance(val, Mapping) and 'href' in val:
            link = cast('Mapping[str, Any]', val)
            result[rel] = Link(href=str(link['href']), templated=bool(link.get('templated', False)))
        elif isinstance(val, list):  # array of links: keep first
            for entry in cast('list[Any]', val):
                if isinstance(entry, Mapping) and 'href' in entry:
                    link = cast('Mapping[str, Any]', entry)
                    result[rel] = Link(href=str(link['href']), templated=bool(link.get('templated', False)))
                    break
    return result


def require_link(links: Mapping[str, Link], rel: str) -> Link:
    """Return the link for ``rel`` or raise :class:`CookidooLinkError`."""
    if rel not in links:
        raise CookidooLinkError(rel)
    return links[rel]


# --- RFC 6570 URI template expansion (Levels 1-4, the subset the API uses) ---

_EXPR = re.compile(r'\{([+#./;?&]?)([^}]+)\}')


def _encode(value: str, allow_reserved: bool) -> str:
    safe = ":/?#[]@!$&'()*+,;=" + _UNRESERVED if allow_reserved else _UNRESERVED
    return quote(str(value), safe=safe)


def expand_uri_template(template: str, variables: Mapping[str, Any]) -> str:  # noqa: C901
    """Expand an RFC 6570 URI template.

    Supports simple ``{var}``, reserved ``{+var}``, fragment ``{#var}``,
    path ``{/var}``, path-style params ``{;var}``, and query ``{?var}`` / ``{&var}``
    operators, including list values and the explode modifier ``{?list*}``.

    The branchiness is inherent to the RFC 6570 operator/value-type matrix.
    """

    def replace(match: re.Match[str]) -> str:  # noqa: C901
        operator = match.group(1)
        varspec = match.group(2)

        sep, prefix, named, allow_reserved = ',', '', False, False
        if operator == '+':
            allow_reserved = True
        elif operator == '#':
            prefix, allow_reserved = '#', True
        elif operator == '.':
            sep, prefix = '.', '.'
        elif operator == '/':
            sep, prefix = '/', '/'
        elif operator == ';':
            sep, prefix, named = ';', ';', True
        elif operator == '?':
            sep, prefix, named = '&', '?', True
        elif operator == '&':
            sep, prefix, named = '&', '&', True

        parts: list[str] = []
        for spec in varspec.split(','):
            explode = spec.endswith('*')
            name = spec[:-1] if explode else spec
            name = re.sub(r':\d+$', '', name)  # ignore prefix modifier length
            if name not in variables or variables[name] is None:
                continue
            value: Any = variables[name]

            if isinstance(value, (list, tuple)):
                seq = cast('list[Any]', value)
                items = [_encode(str(v), allow_reserved) for v in seq if v is not None]
                if not items:
                    continue
                if named:
                    if explode:
                        parts.extend(f'{name}={v}' for v in items)
                    else:
                        parts.append(f'{name}={",".join(items)}')
                else:
                    parts.append((sep if explode else ',').join(items))
            elif isinstance(value, dict):
                mapping = cast('dict[str, Any]', value)
                pairs = [(str(k), _encode(str(v), allow_reserved)) for k, v in mapping.items() if v is not None]
                if explode:
                    parts.extend(f'{k}={v}' for k, v in pairs)
                else:
                    flat = ','.join(f'{k},{v}' for k, v in pairs)
                    parts.append(f'{name}={flat}' if named else flat)
            else:
                enc = _encode(str(value), allow_reserved)
                if named:
                    parts.append(f'{name}={enc}' if enc != '' else name)
                else:
                    parts.append(enc)

        if not parts:
            return ''
        return prefix + sep.join(parts)

    return _EXPR.sub(replace, template)
