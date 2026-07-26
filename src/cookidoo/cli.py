"""Agent-friendly command-line interface for Cookidoo.

Covers the app's five main tabs — **Para ti** (`for-you`), **Navegar**
(`search` / `recipe`), **Mis recetas** (`my-recipes` / `collections`),
**Mi semana** (`week`), and **Compras** (`shopping`) — plus auth and notes.

Design for automation:
- Output is JSON when stdout is not a TTY (or with ``--json``); a human-readable
  view is shown in a terminal (or with ``--pretty``).
- Credentials come from ``COOKIDOO_USERNAME`` / ``COOKIDOO_PASSWORD`` (and
  ``COOKIDOO_MARKET``); the bearer token is cached so repeated calls don't re-login.
- Errors are emitted as ``{"error": ...}`` on stderr with a non-zero exit code.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

try:
    import typer
    from rich.console import Console
    from rich.table import Table
except ModuleNotFoundError as exc:  # pragma: no cover
    raise SystemExit("The CLI needs the 'cli' extra: pip install 'cookidoo[cli]'") from exc

from .auth import Token
from .client import CookidooClient
from .exceptions import CookidooConfigError, CookidooError

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help='Unofficial Cookidoo (Thermomix) CLI — the five app tabs, agent-friendly.',
)
_out = Console()
_err = Console(stderr=True)


class _State:
    market: str = os.environ.get('COOKIDOO_MARKET', 'xp')
    json: bool = not sys.stdout.isatty()


STATE = _State()

# sentinel: "option not supplied" (distinct from an explicit None)
_MISSING: Any = object()


@app.callback()
def configure(
    market: str | None = typer.Option(
        None, '--market', '-m', help='Market code (de, gb, us, ch, mx, xp…). Env: COOKIDOO_MARKET.'
    ),
    json_out: bool | None = typer.Option(
        None, '--json/--pretty', help='Force JSON or human-readable output (default: auto by TTY).'
    ),
) -> None:
    """Configure global options."""
    if market:
        STATE.market = market
    if json_out is not None:
        STATE.json = json_out


# --------------------------------------------------------------------------- output


def emit(payload: Any, *, table: Table | None = None) -> None:
    """Print a result as JSON (agents) or a rich view (humans)."""
    if STATE.json:
        print(json.dumps(payload, ensure_ascii=False, default=str))
    elif table is not None:
        _out.print(table)
    else:
        _out.print_json(json.dumps(payload, ensure_ascii=False, default=str))


def _fail(message: str, code: int = 1) -> None:
    _err.print(json.dumps({'error': message}, ensure_ascii=False))
    raise typer.Exit(code)


# --------------------------------------------------------------------------- session


def _cache_file(market: str, user: str) -> Path:
    base = Path(os.environ.get('XDG_CACHE_HOME', Path.home() / '.cache')) / 'cookidoo'
    digest = hashlib.sha256(user.encode()).hexdigest()[:8]
    return base / f'{market}_{digest}.json'


def _load_token(market: str, user: str) -> Token | None:
    path = _cache_file(market, user)
    if not path.exists():
        return None
    try:
        return Token.from_dict(json.loads(path.read_text()))
    except (json.JSONDecodeError, KeyError, OSError):
        return None


def _save_token(market: str, user: str, token: Token) -> None:
    path = _cache_file(market, user)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(token.to_dict()))
    path.chmod(0o600)


@asynccontextmanager
async def _session() -> AsyncGenerator[CookidooClient]:
    user = os.environ.get('COOKIDOO_USERNAME')
    password = os.environ.get('COOKIDOO_PASSWORD')
    if not user or not password:
        raise CookidooConfigError('Set COOKIDOO_USERNAME and COOKIDOO_PASSWORD in the environment.')
    token = _load_token(STATE.market, user)
    cc = CookidooClient(user, password, market=STATE.market, token=token)
    try:
        await cc.ensure_token()
        yield cc
    finally:
        if cc.token is not None:
            _save_token(STATE.market, user, cc.token)
        await cc.aclose()


def _run[T](coro: Callable[[CookidooClient], Awaitable[T]]) -> T:
    async def _wrapped() -> T:
        async with _session() as cc:
            return await coro(cc)

    try:
        return asyncio.run(_wrapped())
    except CookidooError as exc:
        _fail(str(exc))
        raise  # unreachable


# --------------------------------------------------------------------------- helpers


def _summary(r: Any) -> dict[str, Any]:
    return {'id': r.id, 'title': r.title, 'rating': r.rating, 'total_time': r.total_time}


def _table(title: str, columns: list[str], rows: list[list[Any]]) -> Table:
    t = Table(title=title, header_style='bold')
    for c in columns:
        t.add_column(c)
    for row in rows:
        t.add_row(*(str(c) for c in row))
    return t


# --------------------------------------------------------------------------- auth / profile


@app.command()
def login() -> None:
    """Authenticate and cache the session token (primes the cache for later calls)."""
    who = _run(lambda cc: cc.get_user_info())
    emit(
        {'email': who.email if who else None, 'country': who.country_of_residence if who else None},
        table=_table('Logged in', ['email', 'country'], [[who.email or '', who.country_of_residence or '']])
        if who
        else None,
    )


@app.command()
def logout() -> None:
    """Delete the cached session token."""
    user = os.environ.get('COOKIDOO_USERNAME', '')
    path = _cache_file(STATE.market, user)
    existed = path.exists()
    path.unlink(missing_ok=True)
    emit({'logged_out': existed})


@app.command()
def whoami() -> None:
    """Show account identity, subscription, devices, and profile preferences."""

    async def _do(cc: CookidooClient) -> dict[str, Any]:
        who = await cc.get_user_info()
        sub = await cc.profile.active_subscription()
        prof = await cc.profile.community_profile()
        devices = await cc.devices.thermomix_versions()
        return {
            'email': who.email if who else None,
            'name': f'{who.given_name} {who.family_name}'.strip() if who else None,
            'country': who.country_of_residence if who else None,
            'roles': list(who.roles) if who else [],
            'username': prof.username,
            'food_preferences': prof.food_preferences,
            'subscription': {'type': sub.type, 'status': sub.status, 'end_date': sub.end_date} if sub else None,
            'devices': devices,
            'market': cc.market.market_code,
        }

    data = _run(_do)
    rows = [[k, str(v)] for k, v in data.items()]
    emit(data, table=_table('whoami', ['field', 'value'], rows))


# --------------------------------------------------------------------------- Para ti


@app.command('for-you')
def for_you(full: bool = typer.Option(False, '--full', help='Include the recipes in each stripe.')) -> None:
    """Para ti — your personalized recommendation carousels."""
    feed = _run(lambda cc: cc.recommendations.for_you())
    stripes: list[dict[str, Any]] = []
    for i, s in enumerate(feed.stripes):
        entry: dict[str, Any] = {'index': i, 'title': s.title, 'topic': s.topic, 'recipe_count': len(s.recipes)}
        if full:
            entry['recipes'] = [_summary(r) for r in s.recipes]
        stripes.append(entry)
    payload = {'consent': feed.consent, 'stripes': stripes}
    table = _table(
        'Para ti',
        ['#', 'title', 'recipes'],
        [[str(s['index']), str(s['title']), str(s['recipe_count'])] for s in stripes],
    )
    emit(payload, table=table)


# --------------------------------------------------------------------------- Navegar


@app.command()
def search(
    query: str = typer.Argument(..., help='Search text.'),
    limit: int = typer.Option(10, '--limit', '-n'),
    languages: str | None = typer.Option(
        None, '--languages', help="Comma-separated language filter; 'all' to search globally."
    ),
) -> None:
    """Navegar — search recipes (auto-scoped to your market's languages)."""
    langs: str | list[str] | None
    if languages is None:
        langs = _MISSING
    elif languages.lower() == 'all':
        langs = None
    else:
        langs = languages.split(',')

    async def _do(cc: CookidooClient) -> dict[str, Any]:
        kwargs: dict[str, Any] = {'limit': limit}
        if langs is not _MISSING:
            kwargs['languages'] = langs
        res = await cc.search.recipes(query, **kwargs)
        return {'query': query, 'count': len(res.recipes), 'results': [_summary(r) for r in res.recipes]}

    data = _run(_do)
    table = _table(
        f'Search: {query}',
        ['id', 'title', 'rating', 'time (s)'],
        [[r['id'], r['title'] or '', f'{r["rating"] or "—"}', str(r['total_time'] or '')] for r in data['results']],
    )
    emit(data, table=table)


@app.command()
def recipe(
    recipe_id: str = typer.Argument(..., help='Recipe id, e.g. r21607.'),
    steps: bool = typer.Option(False, '--steps', help='Include guided-cooking steps.'),
    nutrition: bool = typer.Option(False, '--nutrition', help='Include nutrition groups (raw).'),
) -> None:
    """Navegar — full recipe details, ratings, and (optionally) guided steps."""

    async def _do(cc: CookidooClient) -> dict[str, Any]:
        rec = await cc.recipes.get(recipe_id)
        rating = await cc.recipes.aggregated_rating(recipe_id)
        data: dict[str, Any] = {
            'id': rec.id,
            'title': rec.title,
            'difficulty': rec.difficulty,
            'locale': rec.locale,
            'thermomix_versions': rec.thermomix_versions,
            'serving_size': rec.serving_size.model_dump(by_alias=True) if rec.serving_size else None,
            'times': [t.model_dump(by_alias=True) for t in rec.times],
            'rating': {'value': rating.rating, 'count': rating.count},
            'ingredient_groups': [
                {'title': g.title, 'ingredients': [i.name for i in g.recipe_ingredients]}
                for g in rec.recipe_ingredient_groups
            ],
        }
        if steps:
            data['step_groups'] = [
                {'title': g.title, 'steps': [s.formatted_text for s in g.recipe_steps]} for g in rec.recipe_step_groups
            ]
        if nutrition:
            data['nutrition_groups'] = rec.nutrition_groups
        return data

    emit(_run(_do))


@app.command()
def rate(
    recipe_id: str = typer.Argument(...),
    stars: int = typer.Argument(..., min=1, max=5, help='Your rating, 1-5.'),
) -> None:
    """Navegar — set your personal star rating for a recipe."""
    _run(lambda cc: cc.recipes.set_user_rating(recipe_id, stars))
    emit({'recipe_id': recipe_id, 'rating': stars})


# --------------------------------------------------------------------------- Mis recetas

my = typer.Typer(no_args_is_help=True, help='Mis recetas — your created recipes.')
app.add_typer(my, name='my-recipes')


@my.command('list')
def my_list() -> None:
    """List your created recipes."""
    recipes = _run(lambda cc: cc.custom_recipes.list())
    data = [{'id': r.id, 'name': r.name, 'status': r.status, 'created_at': r.created_at} for r in recipes]
    emit(
        data,
        table=_table(
            'Mis recetas', ['id', 'name', 'status'], [[r['id'] or '', r['name'] or '', r['status'] or ''] for r in data]
        ),
    )


@my.command('show')
def my_show(recipe_id: str = typer.Argument(...)) -> None:
    """Show one of your created recipes."""
    rec = _run(lambda cc: cc.custom_recipes.get(recipe_id))
    emit(rec.model_dump(by_alias=True))


@my.command('create')
def my_create(name: str = typer.Argument(..., help='Recipe name.')) -> None:
    """Create a new (blank) created recipe."""
    rec = _run(lambda cc: cc.custom_recipes.create(name))
    emit({'id': rec.id, 'name': rec.name, 'status': rec.status})


@my.command('delete')
def my_delete(recipe_id: str = typer.Argument(...)) -> None:
    """Delete one of your created recipes."""
    _run(lambda cc: cc.custom_recipes.delete(recipe_id))
    emit({'deleted': recipe_id})


# --------------------------------------------------------------------------- collections (Mis recetas)

col = typer.Typer(no_args_is_help=True, help='Mis recetas — your collections / lists.')
app.add_typer(col, name='collections')


@col.command('list')
def col_list(page: int = typer.Option(0, '--page')) -> None:
    """List your custom collections."""
    lists = _run(lambda cc: cc.collections.custom_lists(page))
    data = [{'id': c.id, 'title': c.title, 'list_type': c.list_type, 'recipes': len(c.all_recipes())} for c in lists]
    emit(
        data,
        table=_table(
            'Collections',
            ['id', 'title', 'recipes'],
            [[c['id'] or '', c['title'] or '', str(c['recipes'])] for c in data],
        ),
    )


@col.command('create')
def col_create(title: str = typer.Argument(...)) -> None:
    """Create a custom collection."""
    c = _run(lambda cc: cc.collections.create_custom_list(title))
    emit({'id': c.id, 'title': c.title})


@col.command('add')
def col_add(
    list_id: str = typer.Argument(...),
    recipe_ids: list[str] = typer.Argument(...),
) -> None:
    """Add recipes to a custom collection."""
    c = _run(lambda cc: cc.collections.add_recipes_to_list(list_id, recipe_ids))
    emit({'id': c.id, 'title': c.title, 'recipes': len(c.all_recipes())})


@col.command('delete')
def col_delete(list_id: str = typer.Argument(...)) -> None:
    """Delete a custom collection."""
    _run(lambda cc: cc.collections.delete_custom_list(list_id))
    emit({'deleted': list_id})


# --------------------------------------------------------------------------- Mi semana

week = typer.Typer(no_args_is_help=True, help='Mi semana — the meal planner.')
app.add_typer(week, name='week')


@week.command('show')
def week_show(
    day: str | None = typer.Argument(None, help='Any date in the week (YYYY-MM-DD; default: today).'),
) -> None:
    """Show the planned recipes for a week."""

    async def _do(cc: CookidooClient) -> dict[str, Any]:
        wk = await cc.planner.get_week(day or datetime.now(tz=UTC).date())
        return {
            'week_of': day or datetime.now(tz=UTC).date().isoformat(),
            'recipe_count': wk.recipe_count,
            'days': [
                {
                    'day': d.day_key,
                    'recipes': [{'id': r.id, 'title': r.title} for r in d.recipes],
                    'custom_recipe_ids': d.customer_recipe_ids,
                }
                for d in wk.my_days
            ],
        }

    data = _run(_do)
    rows = [[str(d['day']), ', '.join(r['title'] or r['id'] for r in d['recipes']) or '—'] for d in data['days']]
    emit(data, table=_table('Mi semana', ['day', 'recipes'], rows))


@week.command('add')
def week_add(
    day: str = typer.Argument(..., help='Date (YYYY-MM-DD).'),
    recipe_ids: list[str] = typer.Argument(...),
    custom: bool = typer.Option(False, '--custom', help='These are created-recipe ids.'),
) -> None:
    """Add recipes to a day in the planner."""
    d = _run(lambda cc: cc.planner.add_recipes(_parse_day(day), recipe_ids, custom=custom))
    emit({'day': d.day_key, 'recipes': [{'id': r.id, 'title': r.title} for r in d.recipes]})


@week.command('remove')
def week_remove(
    day: str = typer.Argument(...),
    recipe_id: str = typer.Argument(...),
    custom: bool = typer.Option(False, '--custom'),
) -> None:
    """Remove a recipe from a day in the planner."""
    _run(lambda cc: cc.planner.remove_recipe(_parse_day(day), recipe_id, custom=custom))
    emit({'day': day, 'removed': recipe_id})


def _parse_day(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise CookidooConfigError(f'Invalid date {value!r}; use YYYY-MM-DD.') from exc


# --------------------------------------------------------------------------- Compras

shopping = typer.Typer(no_args_is_help=True, help='Compras — the shopping list.')
app.add_typer(shopping, name='shopping')


@shopping.command('list')
def shopping_list() -> None:
    """Show the shopping list (ingredients + additional items)."""

    async def _do(cc: CookidooClient) -> dict[str, Any]:
        sl = await cc.shopping.get_list()
        return {
            'recipe_count': len(sl.recipes),
            'ingredients': [
                {
                    'id': i.id,
                    'name': i.name,
                    'quantity': i.quantity.value if i.quantity else None,
                    'unit': i.unit_notation,
                    'owned': i.is_owned,
                }
                for i in sl.ingredients()
            ],
            'additional_items': [{'id': a.id, 'name': a.name, 'owned': a.is_owned} for a in sl.additional_items],
        }

    data = _run(_do)
    rows = [
        [str(i['id']), f'{i["name"]}', f'{i["quantity"] or ""} {i["unit"] or ""}'.strip(), '✓' if i['owned'] else '']
        for i in data['ingredients']
    ]
    emit(data, table=_table(f'Compras ({data["recipe_count"]} recipes)', ['id', 'item', 'qty', 'owned'], rows))


@shopping.command('add-recipes')
def shopping_add_recipes(recipe_ids: list[str] = typer.Argument(...)) -> None:
    """Add recipe ingredients to the shopping list."""
    _run(lambda cc: cc.shopping.add_recipes(recipe_ids))
    emit({'added_recipes': recipe_ids})


@shopping.command('add')
def shopping_add(items: list[str] = typer.Argument(..., help='Free-text item names.')) -> None:
    """Add free-text items to the shopping list."""
    added = _run(lambda cc: cc.shopping.add_additional_items(items))
    emit([{'id': a.id, 'name': a.name} for a in added])


@shopping.command('check')
def shopping_check(
    ids: list[str] = typer.Argument(...),
    additional: bool = typer.Option(False, '--additional', '-a', help='IDs are additional items.'),
    off: bool = typer.Option(False, '--off', help='Uncheck instead of check.'),
) -> None:
    """Mark shopping-list items as owned (checked off)."""
    owned = not off
    pairs = [(i, owned) for i in ids]
    if additional:
        _run(lambda cc: cc.shopping.set_additional_item_ownership(pairs))
    else:
        _run(lambda cc: cc.shopping.set_ingredient_ownership(pairs))
    emit({'updated': ids, 'owned': owned})


@shopping.command('remove')
def shopping_remove(
    ids: list[str] = typer.Argument(...),
    recipes: bool = typer.Option(False, '--recipes', help='IDs are recipe ids (remove their ingredients).'),
) -> None:
    """Remove items (additional items by default, or recipes with --recipes)."""
    if recipes:
        _run(lambda cc: cc.shopping.remove_recipes(ids))
    else:
        _run(lambda cc: cc.shopping.remove_additional_items(ids))
    emit({'removed': ids})


@shopping.command('clear')
def shopping_clear(
    yes: bool = typer.Option(False, '--yes', '-y', help='Confirm clearing the whole list.'),
) -> None:
    """Remove everything from the shopping list."""
    if not yes:
        _fail('Refusing to clear without --yes.')
    _run(lambda cc: cc.shopping.clear())
    emit({'cleared': True})


# --------------------------------------------------------------------------- notes

notes = typer.Typer(no_args_is_help=True, help='Personal recipe notes.')
app.add_typer(notes, name='notes')


@notes.command('get')
def notes_get(recipe_id: str = typer.Argument(...)) -> None:
    """Get your note for a recipe."""
    note = _run(lambda cc: cc.recipes.get_note(recipe_id))
    emit(note.model_dump(by_alias=True) if note else None)


@notes.command('set')
def notes_set(recipe_id: str = typer.Argument(...), text: str = typer.Argument(...)) -> None:
    """Create or update your note for a recipe."""

    async def _do(cc: CookidooClient) -> Any:
        if await cc.recipes.get_note(recipe_id) is not None:
            return await cc.recipes.update_note(recipe_id, text)
        return await cc.recipes.create_note(recipe_id, text)

    note = _run(_do)
    emit(note.model_dump(by_alias=True))


@notes.command('delete')
def notes_delete(recipe_id: str = typer.Argument(...)) -> None:
    """Delete your note for a recipe."""
    _run(lambda cc: cc.recipes.delete_note(recipe_id))
    emit({'deleted': recipe_id})


if __name__ == '__main__':  # pragma: no cover
    app()
