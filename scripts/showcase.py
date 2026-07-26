"""A live showcase of capabilities the web-based original SDK can't reach.

Read-mostly; the one write (a recipe note) is created and then deleted.
"""

import asyncio
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))


def load_env(path: str) -> None:
    p = pathlib.Path(path)
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        line = line.removeprefix("export ")
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


load_env("/home/DouweM/dev/cookidoo-re/.env")

from cookidoo import CookidooClient


def h(title: str) -> None:
    print(f"\n\033[1m{'─' * 3} {title} {'─' * (60 - len(title))}\033[0m")


def stars(rating: float | None) -> str:
    if not rating:
        return "—"
    full = round(rating)
    return "★" * full + "☆" * (5 - full) + f"  {rating:.2f}"


async def main() -> None:
    async with CookidooClient(os.environ["COOKIDOO_USERNAME"], os.environ["COOKIDOO_PASSWORD"], market="mx") as cc:
        tok = await cc.login()
        me = tok.user

        h("🔐 Native token session  (web SDK: scrapes cookies)")
        assert me is not None
        print(f"  Signed in as {me.given_name} {me.family_name} <{me.email}>")
        print(f"  Country: {me.country_of_residence}   Roles: {', '.join(me.roles)}")
        print(
            f"  Real OAuth2 bearer token, {int(tok.expires_at - __import__('time').time()) // 3600}h validity, "
            f"refreshable: {bool(tok.refresh_token)}  (identity decoded from id_token, zero extra calls)"
        )

        h("🌐 Whole-app API surface, discovered live via HAL")
        root = await cc.root_links()
        services = sorted(r.split(":", 1)[-1] for r in root if r.startswith("tmde2:"))
        print(f"  {len(services)} top-level services your account can reach:")
        print("   ", ", ".join(services))

        h("🍳 Your Thermomix setup  (web SDK: no device access)")
        print(f"  Registered devices : {await cc.devices.thermomix_versions() or 'none'}")
        print(f"  Accessories        : {await cc.devices.accessory_ids() or 'none'}")
        sub = await cc.profile.active_subscription()
        if sub:
            print(
                f"  Subscription       : {sub.type} · {sub.status} · until {sub.end_date} · auto-renew={sub.auto_renewing}"
            )

        h("👤 Who the API thinks you are  (community profile)")
        prof = await cc.profile.community_profile()
        print(f"  Username           : {prof.username}   public={prof.is_public}")
        print(f"  Food preferences   : {prof.food_preferences or 'none set'}")
        print(f"  Saved searches     : {len(prof.saved_searches)}")

        h('✨ Personalized "For You"  (web SDK: none of this)')
        feed = await cc.recommendations.for_you()
        print(f"  {len(feed.stripes)} carousels tuned to you (consent={feed.consent}):")
        for s in feed.stripes:
            sample = ", ".join(r.title or "?" for r in s.recipes[:3])
            print(f"   • {s.title}  ({len(s.recipes)} recipes)  e.g. {sample}")

        h("🔬 Deep-dive a recommended recipe  (rating + nutrition + similar)")
        pick = next((r for st in feed.stripes for r in st.recipes if r.id), None)
        if pick:
            rec = await cc.recipes.get(pick.id)
            n_ing = sum(len(g.recipe_ingredients) for g in rec.recipe_ingredient_groups)
            n_steps = sum(len(g.recipe_steps) for g in rec.recipe_step_groups)
            rating = await cc.recipes.aggregated_rating(pick.id)
            print(f'  "{rec.title}"  ({rec.id})')
            print(
                f"    difficulty={rec.difficulty}  devices={rec.thermomix_versions}  "
                f"ingredients={n_ing}  guided steps={n_steps}"
            )
            print(f"    community rating: {stars(rating.rating)}  ({rating.count} ratings)")
            if rec.nutrition_groups:
                nuts = (
                    rec.nutrition_groups[0].get("recipeNutritions", [])
                    if isinstance(rec.nutrition_groups[0], dict)
                    else []
                )
                labels = [n.get("type") or n.get("name") for n in nuts[:6] if isinstance(n, dict)]
                if labels:
                    print(f"    nutrition tracked : {', '.join(str(x) for x in labels)}")
            similar = await cc.recommendations.similar(pick.id)
            if similar:
                print(f"    more like this    : {', '.join(r.title or '?' for r in similar[:3])}")

        h("📝 Personal recipe notes  (web SDK: cannot)")
        if pick:
            note = await cc.recipes.create_note(pick.id, "Try with smoked paprika next time 🌶️  — added via SDK")
            got = await cc.recipes.get_note(pick.id)
            print(f"  wrote note on {pick.id}: “{got.text if got else note.text}”")
            await cc.recipes.delete_note(pick.id)
            print(f"  cleaned up (note deleted): {await cc.recipes.get_note(pick.id) is None}")

        h("🥗 Preference-aware search  (auto-scoped to your languages)")
        pref = (prof.food_preferences or ["dinner"])[0]
        res = await cc.search.recipes(pref, limit=5)
        print(f'  top "{pref}" recipes for you: ')
        for r in res.recipes[:5]:
            print(f"   • {r.title}  ({r.rating}★, {r.total_time or '?'}s)")

        h("🤖 Cookidoo AI assistant tips  (web SDK: none)")
        try:
            tips = await cc.assistant.tips()
            import json

            blob = json.dumps(tips, ensure_ascii=False)
            print(f"  copilot tips payload: {blob[:200]}{'…' if len(blob) > 200 else ''}")
        except Exception as e:  # noqa: BLE001
            print(f"  (assistant tips unavailable: {e})")

        h("🎛️  App feature flags the server sets for you")
        toggles = await cc.config.feature_toggles()
        interesting = [
            k
            for k in toggles
            if any(w in k.lower() for w in ("foryou", "assistant", "copilot", "rating", "device", "shopping", "search"))
        ]
        print(f"  {len(toggles)} feature toggles; a few of note:")
        for k in interesting[:8]:
            print(f"   • {k}")

        print("\n\033[1m✅ Everything above ran live against your account through the native mobile API.\033[0m")


asyncio.run(main())
