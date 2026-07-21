#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / 'deploy/wwcx-admin-electrum/templates/electrum.php'
API = ROOT / 'deploy/wwcx-admin-electrum/templates/api/electrum-status.php'

for path in (PAGE, API):
    if not path.is_file():
        raise SystemExit(f'Missing required file: {path.relative_to(ROOT)}')

page = PAGE.read_text(encoding='utf-8')
api = API.read_text(encoding='utf-8')

required_page = [
    "wwcx_require_user('admin')",
    "api/electrum-status.php",
    "Read-only watch-wallet monitoring",
    "cache:'no-store'",
]
required_api = [
    "require dirname(__DIR__, 2) . '/includes/store-lib.php'",
    "wwcx_session_start()",
    "wwcx_require_user('admin')",
    "Cache-Control: no-store, private",
    "ELECTRUM_API_BASE_URL",
    "ELECTRUM_API_TOKEN",
    "'/v1/wallet/info'",
    "'/v1/wallet/balance'",
    "scheme'] ?? '') !== 'https'",
    "'verify_peer' => true",
    "'verify_peer_name' => true",
    "'follow_location' => 0",
    "'max_redirects' => 0",
]
for needle in required_page:
    if needle not in page:
        raise SystemExit(f'Page requirement missing: {needle}')
for needle in required_api:
    if needle not in api:
        raise SystemExit(f'API requirement missing: {needle}')

for forbidden in ('seed phrase', 'private key input', 'sendtoaddress', 'payto', 'broadcast'):
    if forbidden in (page + api).lower():
        raise SystemExit(f'Forbidden spending capability found: {forbidden}')

print('WW.CX Electrum admin module validation passed')
print('admin authorization: present')
print('server-side proxy: present')
print('HTTPS and certificate verification: present')
print('redirect forwarding: disabled')
print('read-only endpoints: 2')
