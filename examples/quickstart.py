"""Quickstart example. Set COOKIDOO_USERNAME/PASSWORD (and optionally COOKIDOO_MARKET)."""

import asyncio
import os

from cookidoo import CookidooClient


async def main() -> None:
    async with CookidooClient(
        os.environ["COOKIDOO_USERNAME"],
        os.environ["COOKIDOO_PASSWORD"],
        market=os.environ.get("COOKIDOO_MARKET", "xp"),
    ) as cc:
        await cc.login()
        me = await cc.get_user_info()
        print(f"Signed in as {me.email} ({me.country_of_residence})")

        sub = await cc.profile.active_subscription()
        print("Subscription:", sub.type if sub else "none", "-", sub.status if sub else "")

        results = await cc.search.recipes("chocolate cake", limit=3)
        for r in results.recipes:
            print(f"  {r.id}  {r.title}  ({r.rating}★)")

        if results.recipes:
            recipe = await cc.recipes.get(results.recipes[0].id)
            n_ing = sum(len(g.recipe_ingredients) for g in recipe.recipe_ingredient_groups)
            n_steps = sum(len(g.recipe_steps) for g in recipe.recipe_step_groups)
            print(
                f"\n{recipe.title}: {n_ing} ingredients, {n_steps} steps, "
                f"difficulty={recipe.difficulty}, devices={recipe.thermomix_versions}"
            )

        feed = await cc.recommendations.for_you()
        print("\nFor You:", ", ".join(s.title or "?" for s in feed.stripes))


if __name__ == "__main__":
    asyncio.run(main())
