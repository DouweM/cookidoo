"""Empirically verify mutating endpoints (verb + body) against the live API.

All operations are reversible and cleaned up. Planner uses a far-future date.
For each endpoint we try the documented verb; on 404/405 we try alternates and
report which verb/body actually worked.
"""

import asyncio
import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'src'))


def le(p):
    for l in pathlib.Path(p).read_text().splitlines():
        l = l.strip()
        if not l or l.startswith('#'):
            continue
        l = l.removeprefix('export ')
        k, _, v = l.partition('=')
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


le('/home/DouweM/dev/cookidoo-re/.env')
from cookidoo import CookidooClient, const
from cookidoo.exceptions import CookidooError, CookidooRequestError

RID = 'r737551'  # a real published recipe


async def try_verbs(cc, url, verbs, json_body=None, accept=None, ct='application/json'):
    """Try each verb until one is accepted; return (verb, status_or_result)."""
    for v in verbs:
        try:
            res = await cc.request_json(v, url, json=json_body, accept=accept, content_type=ct)
            return v, 'OK', res
        except CookidooRequestError as e:
            if e.status in (404, 405, 400):
                continue
            return v, f'ERR {e.status}', None
        except CookidooError as e:
            return v, f'ERR {e}', None
    return None, 'all verbs failed', None


async def main():
    async with CookidooClient(os.environ['COOKIDOO_USERNAME'], os.environ['COOKIDOO_PASSWORD'], market='mx') as cc:
        await cc.login()

        print('== PLANNER add/remove (far-future 2027-01-15) ==')
        day = '2027-01-15'
        add_url = await cc.resolve(const.Rel.PLANNING, 'planning:api-my-day')
        verb, status, res = await try_verbs(
            cc,
            add_url,
            ['POST', 'PUT'],
            json_body={'dayKey': day, 'recipeIds': [RID]},
            accept=const.MEDIA_PLANNING_MY_DAY,
        )
        print(f'  add my-day: verb={verb} {status}')
        if status == 'OK':
            wk = await cc.planner.get_week(day)
            print(f'  verify: recipeCount={wk.recipe_count}')
            rm_url = await cc.resolve(
                const.Rel.PLANNING, 'planning:api-remove-recipe', dayKey=day, recipeId=RID, recipeSource=None
            )
            try:
                await cc.request_json('DELETE', rm_url, accept=const.MEDIA_PLANNING_MY_DAY)
                print('  removed: OK')
            except CookidooError as e:
                print('  remove FAILED:', e)

        print('== RECIPE NOTES create/get/delete ==')
        create_url = await cc.resolve(const.Rel.RECIPE_NOTES, 'recipe-notes:recipe-note-create')
        for body in (
            {'recipeId': RID, 'note': 'sdk probe'},
            {'recipeId': RID, 'text': 'sdk probe'},
            {'recipeId': RID, 'content': 'sdk probe'},
        ):
            verb, status, res = await try_verbs(cc, create_url, ['POST'], json_body=body)
            print(f'  create note body={list(body)[1]}: {status}')
            if status == 'OK':
                note = await cc.recipes.get_note(RID)
                print('  get note:', json.dumps(note, ensure_ascii=False)[:150] if note else note)
                del_url = await cc.resolve(const.Rel.RECIPE_NOTES, 'recipe-notes:recipe-note', recipeId=RID)
                try:
                    await cc.request_json('DELETE', del_url)
                    print('  deleted note: OK')
                except CookidooError as e:
                    print('  delete note FAILED:', e)
                break

        print('== CUSTOM LIST create/delete ==')
        cl_url = await cc.resolve(const.Rel.ORGANIZE, 'organize:api-custom-list')
        verb, status, res = await try_verbs(
            cc, cl_url, ['POST', 'PUT'], json_body={'title': '__sdk_probe__'}, accept=const.MEDIA_CUSTOM_LIST
        )
        print(f'  create custom-list: verb={verb} {status}')
        if status == 'OK':
            content = res.get('content', res) if isinstance(res, dict) else res
            lid = (content or {}).get('id') or (content or {}).get('customlistId')
            print('  new list id:', lid)
            if lid:
                try:
                    await cc.request_json('DELETE', cl_url + f'/{lid}', accept=const.MEDIA_CUSTOM_LIST)
                    print('  deleted list: OK')
                except CookidooError as e:
                    print('  delete list FAILED:', e)

        print('== SHOPPING add_recipes/remove ==')
        before = len((await cc.shopping.get_list()).recipes)
        add_url = await cc.resolve(const.Rel.PANTRY, 'pantry:recipe-ingredients')
        verb, status, res = await try_verbs(cc, add_url, ['POST'], json_body={'recipeIDs': [RID]})
        print(f'  add recipe ingredients: {status}')
        if status == 'OK':
            after = len((await cc.shopping.get_list()).recipes)
            print(f'  recipes {before} -> {after}')
            rm_url = await cc.resolve(const.Rel.PANTRY, 'pantry:remove-recipe')
            try:
                await cc.request_json('POST', rm_url, json={'recipeIDs': [RID]}, content_type='application/json')
                print('  removed recipe: OK, now', len((await cc.shopping.get_list()).recipes))
            except CookidooError as e:
                print('  remove FAILED:', e)


asyncio.run(main())
