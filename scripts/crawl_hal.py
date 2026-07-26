"""Crawl the live HAL tree (root + sub-home-documents) to map the real surface.

Read-only: only GETs documents whose links are non-templated (i.e. safe home /
config documents). Templated links are recorded but not fetched.
"""

import asyncio
import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'src'))


def load_env(path):
    for line in pathlib.Path(path).read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        line = line.removeprefix('export ')
        k, _, v = line.partition('=')
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


load_env('/home/DouweM/dev/cookidoo-re/.env')
from cookidoo import CookidooClient
from cookidoo.const import HOME_ACCEPT
from cookidoo.exceptions import CookidooError
from cookidoo.hal import parse_links


async def main():
    out = {}
    async with CookidooClient(os.environ['COOKIDOO_USERNAME'], os.environ['COOKIDOO_PASSWORD'], market='mx') as cc:
        await cc.login()
        root = await cc.root_links()
        out['_root'] = {rel: {'href': l.href, 'templated': l.templated} for rel, l in root.items()}
        print(f'ROOT: {len(root)} relations')
        for rel, link in root.items():
            if rel in ('self', 'curies'):
                continue
            if link.templated:
                print(f'  [tmpl] {rel}: {link.href}')
                continue
            try:
                doc = await cc.request_json('GET', link.href, accept=HOME_ACCEPT)
            except CookidooError as e:
                out[rel] = {'error': repr(e)}
                print(f'  [ERR ] {rel}: {e}')
                continue
            if isinstance(doc, dict) and '_links' in doc:
                sub = parse_links(doc)
                out[rel] = {r: {'href': l.href, 'templated': l.templated} for r, l in sub.items()}
                print(
                    f'  [home] {rel}: {len(sub)} sub-links -> {[r for r in list(sub) if r not in ("self", "curies")][:12]}'
                )
            else:
                keys = list(doc)[:12] if isinstance(doc, dict) else type(doc).__name__
                out[rel] = {'_non_hal_keys': keys}
                print(f'  [data] {rel}: keys={keys}')
    pathlib.Path('/home/DouweM/dev/cookidoo-re/research/live_hal_map.json').write_text(json.dumps(out, indent=2))
    print('\nsaved -> research/live_hal_map.json')


asyncio.run(main())
