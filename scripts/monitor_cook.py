"""Live TM6 cooking-status monitor via Firebase Cloud Messaging push.

Registers as an FCM client using the app's Firebase project, registers that token
with Cookidoo's RMI/IoT gateway, then prints each cooking-status push as JSON.
"""

import asyncio
import json
import logging
import os
import pathlib
import sys
import uuid

logging.basicConfig(level=logging.WARNING, format='%(levelname)s %(name)s: %(message)s', stream=sys.stdout)
logging.getLogger('firebase_messaging').setLevel(logging.WARNING)

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'src'))


def load_env(path: str) -> None:
    p = pathlib.Path(path)
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        line = line.removeprefix('export ')
        k, _, v = line.partition('=')
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


load_env('/home/DouweM/dev/cookidoo-re/.env')

from firebase_messaging import FcmPushClient, FcmRegisterConfig

from cookidoo import CookidooClient

# App Firebase project (extracted from the decompiled APK resources).
FCM = FcmRegisterConfig(
    project_id='cookidoo-app',
    app_id='1:447648593759:android:ebfbf2b01378844b',
    api_key='AIzaSyCPyZm8EAdpVhWhNLFv3cOw_Kx4iNxR_E4',
    messaging_sender_id='447648593759',
    bundle_id='com.vorwerk.cookidoo',
)
RMI_HEADER = {'rmi-api-version': '2026-06-01'}
STATE_DIR = pathlib.Path.home() / '.cache' / 'cookidoo'
CREDS_FILE = STATE_DIR / 'fcm_creds.json'
APPID_FILE = STATE_DIR / 'mobile_app_id.txt'


def log(msg: str) -> None:
    print(msg, flush=True)


def on_message(notification: dict, persistent_id: str, _ctx: object) -> None:
    data = notification.get('data', notification) if isinstance(notification, dict) else notification
    log('🔔 COOKING STATUS  ' + json.dumps(data, ensure_ascii=False))


async def main() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    creds = json.loads(CREDS_FILE.read_text()) if CREDS_FILE.exists() else None
    mobile_app_id = APPID_FILE.read_text().strip() if APPID_FILE.exists() else str(uuid.uuid4())
    APPID_FILE.write_text(mobile_app_id)

    def save_creds(updated: dict) -> None:
        CREDS_FILE.write_text(json.dumps(updated))

    log('① Registering with Firebase Cloud Messaging…')
    client = FcmPushClient(on_message, FCM, creds, save_creds)
    fcm_token = await client.checkin_or_register()
    log(f'   FCM token acquired: {fcm_token[:24]}…')

    async with CookidooClient(os.environ['COOKIDOO_USERNAME'], os.environ['COOKIDOO_PASSWORD'], market='mx') as cc:
        await cc.login()
        reg_url = await cc.resolve('tmde2:rmi-config', 'rmi:register-token')
        token = await cc.ensure_token()
        body = {'token': fcm_token, 'bundleId': 'com.vorwerk.cookidoo', 'platform': 'AN', 'mobileAppId': mobile_app_id}
        log(f'② Registering token with Cookidoo IoT gateway ({reg_url})…')
        resp = await cc._http.post(
            reg_url,
            json=body,
            headers={'Authorization': f'Bearer {token.access_token}', 'Content-Type': 'application/json', **RMI_HEADER},
        )
        log(f'   register-token -> HTTP {resp.status_code} {resp.text[:200]}')

        # Try to list monitorable devices (best-effort; may 400).
        for nonce in (mobile_app_id, str(uuid.uuid4())):
            dev_url = await cc.resolve('tmde2:rmi-config', 'rmi:devices', nonce=nonce)
            r = await cc._http.get(dev_url, headers={'Authorization': f'Bearer {token.access_token}', **RMI_HEADER})
            log(f'   rmi:devices (nonce={nonce[:8]}…) -> HTTP {r.status_code} {r.text[:160]}')
            if r.status_code == 200:
                break

        log('③ Listening for cooking-status pushes… (interact with the TM6 to trigger an event)')
        await client.start()
        while True:
            await asyncio.sleep(5)


if __name__ == '__main__':
    asyncio.run(main())
