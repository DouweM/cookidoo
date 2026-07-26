# cookidoo — comprehensive async Python SDK for the Cookidoo® (Thermomix®) mobile API

An unofficial, fully-typed async Python client for **Cookidoo**, reverse-engineered
from the official Android app (`com.vorwerk.cookidoo` **v26.6.19**). Unlike existing
libraries, this targets the app's **native mobile API gateway** with proper
**bearer-token OAuth2 (PKCE)** auth and **HAL hypermedia** navigation — covering the
*entire* surface the app itself uses, not just the shopping list.

> Not affiliated with or endorsed by Vorwerk / Cookidoo. For personal use with your
> own account. Cookidoo and Thermomix are trademarks of Vorwerk.

## Why this exists

The known ecosystem ([`miaucl/cookidoo-api`](https://github.com/miaucl/cookidoo-api)
— which powers Home Assistant — plus assorted MCP servers and CLIs) talks to the
**website** (`cookidoo.<tld>`) and authenticates by **scraping login cookies**
(`_oauth2_proxy`). This SDK instead uses what the app uses:

| | Existing web SDKs | This SDK (mobile) |
|---|---|---|
| Host | `https://cookidoo.<tld>` (website) | `https://<market>.tmmobile.vorwerk-digital.com` (mobile gateway) |
| Auth | scrape session cookies | native **OAuth2 PKCE** → `Authorization: Bearer` + refresh token |
| API shape | hand-coded paths | **HAL** home-document discovery (auto-adapts) |
| Surface | shopping list, search, recipe, calendar, collections | **all of the above + ratings, recipe notes, recommendations/For-You, custom recipes, devices, AI assistant (copilot), notifications, consent, feature config, purchases…** |

## Install

```bash
pip install cookidoo         # or, from a clone: pip install -e .
```
Requires Python ≥ 3.13. Depends only on `httpx` and `pydantic>=2`.

## Quickstart

```python
import asyncio
from cookidoo import CookidooClient


async def main():
    async with CookidooClient('you@example.com', 'password', market='mx') as cc:
        await cc.login()  # PKCE OAuth2, discovers endpoints via HAL
        me = await cc.get_user_info()  # decoded from id_token, no extra call
        print(me.email, me.country_of_residence, me.roles)

        # search + full recipe
        hits = await cc.search.recipes('pasta', limit=5)
        recipe = await cc.recipes.get(hits.recipes[0].id)
        print(recipe.title, recipe.difficulty, recipe.thermomix_versions)
        for group in recipe.recipe_ingredient_groups:
            for ing in group.recipe_ingredients:
                print(' -', ing.name, ing.quantity.value if ing.quantity else '', ing.unit_notation)

        # shopping list
        sl = await cc.shopping.get_list()
        print(len(sl.ingredients()), 'ingredients on the list')

        # meal planner
        week = await cc.planner.get_week()  # this week
        # personalized For You feed
        feed = await cc.recommendations.for_you()
        print([s.title for s in feed.stripes])


asyncio.run(main())
```

`market` is your account's market code (`de`, `gb`, `us`, `ch`, `mx`, `xp` for
international, …). See `cookidoo.all_markets()`. The client auto-refreshes the token
and retries once on a 401.

## API surface

Everything hangs off resource namespaces on the client. Each returns typed Pydantic
models; every model keeps unmapped fields in `.model_extra`.

### `cc.recipes`
- `get(recipe_id) -> Recipe` — full detail: ingredient groups, step groups (guided
  cooking text), nutrition, times, serving size, devices/accessories, assets, tags.
- `variants(cluster_id)` — TM5/TM6/TM7 renditions.
- `collections_of(recipe_id)` — managed collections containing it.
- `aggregated_rating(recipe_id) -> AggregatedRating`, `user_rating` / `set_user_rating`.
- `get_note` / `create_note` / `update_note` / `delete_note` — **personal recipe notes**.

### `cc.search`
- `recipes(query, *, languages=..., filters=..., limit=..., pagination=...) -> SearchResult`.
  Results default to your **market's content languages** (e.g. `es-MX,es,en` for `mx`) —
  matching the app; the API otherwise returns recipes in *every* language. Pass
  `languages=None` to search globally, or an explicit list to override.
- `ingredients(query)`

### `cc.shopping`  (the "pantry" service)
- `get_list() -> ShoppingList` (`.ingredients()` flattens all items).
- `add_recipes` / `add_custom_recipes` / `remove_recipes`.
- `add_additional_items` / `edit_additional_items` / `remove_additional_items`.
- `set_ingredient_ownership` / `set_additional_item_ownership` (tick items off).
- `clear()`.

### `cc.planner`
- `get_week(day=today) -> CalendarWeek`
- `add_recipes(day, recipe_ids, custom=False)` (verified: HTTP PUT) / `remove_recipe(...)`.

### `cc.collections`  (the "organize" service)
- `custom_lists` / `create_custom_list` / `add_recipes_to_list` / `delete_custom_list`.
- `bookmarks`, `get_by_code(share_code)`.

### `cc.custom_recipes`
- `list` / `get` / `create` / `delete` your own created recipes.

### `cc.recommendations`
- `for_you() -> ForYouFeed` (personalized carousels/"stripes"), `similar(recipe_id)`.

### `cc.profile`
- `community_profile() -> CommunityProfile`, `saved_searches()`.
- `subscriptions() -> [Subscription]`, `active_subscription()`, `me()`.

### `cc.devices`
- `thermomix_versions()`, `accessory_ids()`.
- **`watch_cooking()`** — an async generator yielding live `CookingStatus` frames
  from a connected Thermomix while it cooks a Guided recipe. It registers as a
  Firebase Cloud Messaging client (the app's push transport), subscribes the token
  with the IoT gateway, and streams `state`, `remaining_seconds`, step text, etc.
  Needs the `monitor` extra (`pip install 'cookidoo[monitor]'`).

  ```python
  async for status in cc.devices.watch_cooking(credentials_path='~/.cache/cookidoo/fcm.json'):
      print(status.state, status.remaining_seconds, status.primary_info)
      if status.finished:
          break
  ```
- `register_push_token(...)` / `unregister_push_token(...)` / `monitored_devices()`
  for lower-level control of the RMI IoT gateway.

### `cc.assistant`  (the "copilot" AI service)
- `tips()` (GET). The chat itself is a hosted WebView in the app, not a JSON API,
  so use `chat_url()` to get the authenticated web URL rather than a `chat()` call.

### `cc.notifications`, `cc.config`
- `notifications.list()`; `config.mobile_config()` / `feature_toggles()`.

### Escape hatch
Anything not wrapped is one line away — resolve any HAL relation and call it:

```python
url = await cc.resolve('tmde2:foundation', 'foundation:subscription')
data = await cc.request_json('GET', url)
# discover everything the API offers for your account:
print(await cc.root_links())  # 31 top-level relations
print(await cc.subdoc_links('tmde2:copilot'))  # assistant endpoints
```

## CLI (agent-friendly)

Install the CLI extra and you get a `cookidoo` command covering the app's five tabs:

```bash
pip install 'cookidoo[cli]'
export COOKIDOO_USERNAME=you@example.com COOKIDOO_PASSWORD=… COOKIDOO_MARKET=mx
```

| App tab | Command |
|---|---|
| **Para ti** | `cookidoo for-you [--full]` |
| **Navegar** | `cookidoo search "tacos" -n 5` · `cookidoo recipe r493976 [--steps] [--nutrition]` |
| **Mis recetas** | `cookidoo my-recipes list\|show\|create\|delete` · `cookidoo collections list\|create\|add\|delete` |
| **Mi semana** | `cookidoo week show [DATE]` · `cookidoo week add 2026-08-01 r493976` · `cookidoo week remove …` |
| **Compras** | `cookidoo shopping list\|add-recipes\|add\|check\|remove\|clear` |
| (extras) | `cookidoo whoami` · `cookidoo rate r493976 5` · `cookidoo notes get\|set\|delete` |
| **live cooking** | `cookidoo monitor [--once] [--timeout N]` — stream your Thermomix's cooking status (needs the `monitor` extra + a device cooking a Guided recipe) |

Built for automation:
- **JSON by default** when stdout isn't a TTY (or `--json`); a rich table view in a terminal (or `--pretty`).
- **Cached bearer token** (`$XDG_CACHE_HOME/cookidoo/…`, mode 600) so repeated agent calls don't re-login — a warm `whoami` returns in well under a second.
- Errors are `{"error": …}` on stderr with a non-zero exit code.

```console
$ cookidoo whoami
{"email": "you@example.com", "country": "MX", "subscription": {"type": "REGULAR", "status": "ACTIVE"}, "devices": ["TM6"], ...}
$ cookidoo search tacos -n 3 | jq -r '.results[] | "\(.id)  \(.title)  \(.rating)★"'
r493976  Beef tacos  4.43★
r919810  Tacos de pollo al pastor  4.3★
r116096  Chilli Tacos  4.7★
```

## Auth details (reverse-engineered)

- OAuth2 **authorization-code + PKCE (S256)**, `client_id=mobile-android`,
  `redirect_uri=com.vorwerk.cookidoo://code-grant`,
  `scope="openid profile email offline offline_access"`.
- Endpoints are **discovered at runtime** from the HAL home document
  (`/.well-known/mobile-home` → `tmde2:auth` → OpenID discovery), so they track the
  live service. On the `mx` market these resolve to
  `ciam.prod.cookidoo.vorwerk-digital.com/authz-srv/authz` and `/token-srv/token`.
- The headless login submits your credentials to the CIAM login form exactly as the
  app's WebView does, captures the `code-grant` redirect, and exchanges the code
  (with the PKCE verifier) for a bearer + refresh token. User identity is decoded
  from the `id_token` JWT — no extra network call.

Persist/restore a session by passing `token=` to the constructor (see `Token`).

## Not covered: the web-only feeds

The root document also advertises `recipe-feed-v2` / `collection-feed-v2` (infinite
discovery feeds). These live on the **web** platform (`web.production-eu…`) and reject
the mobile bearer token (HTTP 401) — the app reaches them through a web-session bridge
(`profile:login-via-web` → `cookidoo.<tld>` cookies), the same mechanism the older
web SDKs use. The native discovery feed is `recommendations.for_you()`, which this SDK
covers. Web-session bridging could be added later to unlock these.

## Development

Uses [uv](https://docs.astral.sh/uv/), ruff, and pyright (strict), matching the
surrounding projects.

```bash
uv sync --group dev --group lint
uv run pytest            # offline unit tests (no credentials needed)
uv run ruff check src tests
uv run pyright src tests
```

Live smoke tests in `scripts/` (`smoke_full.py`, `probe_mutations.py`) read
`COOKIDOO_USERNAME` / `COOKIDOO_PASSWORD` from a `.env` file and exercise the real API.

See [`research/`](research) for the full reverse-engineering notes: the decoded
HAL surface (`live_hal_map.json`), per-feature endpoint contracts (`re/*.md`), and the
authoritative market table (`localization_config.json`).
