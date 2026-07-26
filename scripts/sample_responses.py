"""Fetch real response samples for the main GET endpoints to ground the models."""

import asyncio
import datetime
import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))


def load_env(path):
    for line in pathlib.Path(path).read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        line = line.removeprefix("export ")
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


load_env("/home/DouweM/dev/cookidoo-re/.env")
from cookidoo import CookidooClient
from cookidoo.const import MEDIA_RECIPE
from cookidoo.exceptions import CookidooError

OUT = pathlib.Path("/home/DouweM/dev/cookidoo-re/research/samples")
OUT.mkdir(exist_ok=True)


def shape(o, depth=0, maxd=4):
    if depth >= maxd:
        return type(o).__name__
    if isinstance(o, dict):
        return {k: shape(v, depth + 1, maxd) for k, v in list(o.items())[:30]}
    if isinstance(o, list):
        return [shape(o[0], depth + 1, maxd)] + (["..(%d)" % len(o)] if len(o) > 1 else []) if o else []
    return type(o).__name__


async def grab(cc, name, root, sub=None, accept=None, **vars):
    try:
        url = await cc.resolve(root, sub, **vars)
        doc = await cc.request_json("GET", url, accept=accept)
        (OUT / f"{name}.json").write_text(json.dumps(doc, indent=1, ensure_ascii=False)[:200000])
        print(f"\n### {name}  [{url}]")
        print(json.dumps(shape(doc), ensure_ascii=False)[:1200])
        return doc
    except CookidooError as e:
        print(f"\n### {name}: ERROR {e}")
        return None


async def main():
    async with CookidooClient(os.environ["COOKIDOO_USERNAME"], os.environ["COOKIDOO_PASSWORD"], market="mx") as cc:
        await cc.login()
        await grab(cc, "subscriptions", "tmde2:ownership", "ownership:subscriptionsV2")
        await grab(cc, "shopping_list", "tmde2:pantry", "pantry:home")
        today = datetime.date.today().isoformat()
        await grab(cc, "planner_week", "tmde2:planning", "planning:api-my-week-enhanced-from-date", dayKey=today)
        foryou = await grab(cc, "foryou", "tmde2:recommender", "recommender:mobile_foryou")
        await grab(cc, "custom_recipes", "tmde2:customer-recipes", "customer-recipes:recipes-list")
        await grab(cc, "community_profile", "tmde2:community-profile", "community-profile:user-private-profile")
        await grab(cc, "user_basic_info", "tmde2:community-profile", "community-profile:user-basic-info")
        await grab(cc, "devices_versions", "tmde2:customer-devices", "customer-devices:thermomix-versions")
        await grab(cc, "accessory_ids", "tmde2:customer-devices", "customer-devices:api-accessory-ids")
        await grab(cc, "notifications", "tmde2:mobile-notification", "mobile:notifications")
        await grab(cc, "mobile_config", "tmde2:mobile-config", "mobile-config:config")
        await grab(cc, "search_pasta", "tmde2:search", "search:searchapi", query="pasta", context="recipes", limit="5")

        # find a recipe id from foryou to sample recipe-scoped endpoints
        rid = None

        def find_ids(o):
            out = []
            if isinstance(o, dict):
                for k, v in o.items():
                    if k in ("id", "recipeId", "recipeID") and isinstance(v, str) and ("Recipe" in v or "recipe" in v):
                        out.append(v)
                    out += find_ids(v)
            elif isinstance(o, list):
                for v in o:
                    out += find_ids(v)
            return out

        ids = find_ids(foryou) if foryou else []
        rid = ids[0] if ids else None
        print("\n>>> sample recipe id:", rid)
        if rid:
            await grab(cc, "recipe_details", "tmde2:recipe-details", "recipe:details", accept=MEDIA_RECIPE, id=rid)
            await grab(cc, "recipe_agg_rating", "tmde2:rating", "rating:aggregated-rating-recipe", recipeId=rid)
            await grab(cc, "recipe_note", "tmde2:recipe-notes", "recipe-notes:recipe-note", recipeId=rid)


asyncio.run(main())
