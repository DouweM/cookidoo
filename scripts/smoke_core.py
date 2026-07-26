"""Live core-flow smoke test: home doc -> OIDC discovery -> login -> user info."""

import asyncio
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
EMAIL = os.environ['COOKIDOO_USERNAME']
PASSWORD = os.environ['COOKIDOO_PASSWORD']

from cookidoo import CookidooClient
from cookidoo.exceptions import CookidooError


async def probe_market(market):
    print(f'\n===== market={market} =====')
    async with CookidooClient(EMAIL, PASSWORD, market=market) as cc:
        print('base_url:', cc.base_url, '| language:', cc.language)
        try:
            links = await cc.root_links()
            print(f'root home doc OK: {len(links)} link relations')
            print('  sample rels:', [r for r in list(links)[:8]])
        except CookidooError as e:
            print('root home doc FAILED:', repr(e))
            return None
        try:
            authz, token_url = await cc.oidc_endpoints()
            print('authorization_endpoint:', authz)
            print('token_endpoint:', token_url)
        except CookidooError as e:
            print('OIDC discovery FAILED:', repr(e))
            return None
        try:
            tok = await cc.login()
            print(
                'LOGIN OK. token_type:',
                tok.token_type,
                'expires_in≈',
                int(tok.expires_at - __import__('time').time()),
                's',
            )
            print('has refresh_token:', bool(tok.refresh_token))
            u = tok.user
            if u:
                print('user:', u.email, '| country_of_residence:', u.country_of_residence, '| roles:', u.roles)
            return market
        except CookidooError as e:
            print('LOGIN FAILED:', repr(e))
            return None


async def main():
    for m in ('mx', 'xp'):
        ok = await probe_market(m)
        if ok:
            print(f'\n✅ working market: {ok}')
            return
    print('\n❌ no market worked')


asyncio.run(main())
