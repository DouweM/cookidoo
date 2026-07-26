"""Comprehensive live smoke test of the resource API (read-only + 1 reversible write)."""

import asyncio
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))


def le(p):
    for l in pathlib.Path(p).read_text().splitlines():
        l = l.strip()
        if not l or l.startswith("#"):
            continue
        l = l.removeprefix("export ")
        k, _, v = l.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


le("/home/DouweM/dev/cookidoo-re/.env")
from cookidoo import CookidooClient


def ok(label, val):
    print(f"  ✅ {label}: {val}")


async def main():
    async with CookidooClient(os.environ["COOKIDOO_USERNAME"], os.environ["COOKIDOO_PASSWORD"], market="mx") as cc:
        await cc.login()
        me = await cc.get_user_info()
        print("AUTH")
        ok("user", f"{me.email} / {me.country_of_residence} / {me.roles}")

        print("PROFILE + OWNERSHIP")
        subs = await cc.profile.subscriptions()
        ok("subscriptions", [f"{s.type}:{s.status} active={s.active}" for s in subs])
        prof = await cc.profile.community_profile()
        ok("community profile", f"user={prof.username} public={prof.is_public} prefs={prof.food_preferences}")

        print("SEARCH + RECIPE")
        res = await cc.search.recipes("pasta", limit=3)
        ok("search 'pasta'", f"{len(res.recipes)} hits; first={res.recipes[0].title!r} ({res.recipes[0].id})")
        rid = res.recipes[0].id
        rec = await cc.recipes.get(rid)
        ok(
            "recipe.get",
            f"{rec.title!r} diff={rec.difficulty} tmv={rec.thermomix_versions} "
            f"ingredients={sum(len(g.recipe_ingredients) for g in rec.recipe_ingredient_groups)} "
            f"steps={sum(len(g.recipe_steps) for g in rec.recipe_step_groups)}",
        )
        rating = await cc.recipes.aggregated_rating(rid)
        ok("aggregated_rating", f"{rating.rating} ({rating.count} ratings)")

        print("SHOPPING LIST")
        sl = await cc.shopping.get_list()
        ok(
            "shopping list",
            f"{len(sl.recipes)} recipes, {len(sl.ingredients())} ingredients, "
            f"{len(sl.additional_items)} additional items",
        )

        print("PLANNER")
        wk = await cc.planner.get_week()
        ok("this week", f"{wk.recipe_count} planned recipes across {len(wk.my_days)} days")

        print("CUSTOM RECIPES")
        cr = await cc.custom_recipes.list()
        ok("custom recipes", [c.name for c in cr])

        print("RECOMMENDATIONS")
        fy = await cc.recommendations.for_you()
        ok("for you", f"consent={fy.consent}, {len(fy.stripes)} stripes: {[s.title for s in fy.stripes][:4]}")

        print("DEVICES")
        ok("thermomix versions", await cc.devices.thermomix_versions())
        ok("accessory ids", await cc.devices.accessory_ids())

        print("CONFIG")
        ft = await cc.config.feature_toggles()
        ok("feature toggles", f"{len(ft)} toggles, e.g. {list(ft)[:5]}")

        print("NOTIFICATIONS")
        ok("notifications", await cc.notifications.list())

        print("REVERSIBLE WRITE (add + remove an additional shopping item)")
        added = await cc.shopping.add_additional_items(["__sdk_test__"])
        ok("added", [(a.id, a.name) for a in added])
        if added and added[0].id:
            await cc.shopping.remove_additional_items([added[0].id])
            ok("removed", added[0].id)

        print("\n🎉 ALL RESOURCE GROUPS EXERCISED SUCCESSFULLY")


asyncio.run(main())
