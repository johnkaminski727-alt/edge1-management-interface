# WW.CX Admin Electrum Module

This package adds a read-only Electrum watch-wallet page to the WW.CX administration console.

## Files

- `templates/electrum.php` — administrator page and browser UI.
- `templates/api/electrum-status.php` — authenticated server-side proxy.

Both files expect the existing WW.CX `admin/bootstrap.php` and `wwcx_require_user('admin')` authorization helper.

## Security boundary

- The module exposes status, wallet information, and balances only.
- The browser never receives the Edge1 bearer token.
- The website never receives an Electrum seed, private key, wallet file, or RPC credential.
- The proxy requires an HTTPS application endpoint. Do not expose Electrum JSON-RPC port 7777.
- Keep the Edge1 Electrum API read-only and restricted to the approved private transport.

## Target paths

Copy the templates to:

```text
/home/wwcxjywl/public_html/admin/electrum.php
/home/wwcxjywl/public_html/admin/api/electrum-status.php
```

Before copying, verify that the live admin bootstrap path and authorization helper match the templates. Back up any existing target files.

## Secret configuration

Create a file outside the public web root, readable only by the PHP runtime account. Recommended path:

```text
/home/wwcxjywl/private/electrum.env
```

Contents:

```text
ELECTRUM_API_BASE_URL=https://PRIVATE-EDGE1-APPLICATION-ENDPOINT
ELECTRUM_API_TOKEN=TRANSFERRED-THROUGH-AN-APPROVED-SECRET-CHANNEL
```

Use mode `0600`. The endpoint must terminate HTTPS and forward only the approved `/v1/wallet/info` and `/v1/wallet/balance` application API paths. Do not point it at Electrum RPC directly.

When the secret file is stored elsewhere, set `WWCX_ELECTRUM_ENV` in the PHP runtime environment to its absolute path.

## Navigation integration

Add an administrator navigation entry that links to:

```text
/admin/electrum.php
```

Use the existing global admin navigation component rather than duplicating a menu in this package.

## Validation

Repository validation:

```bash
python3 tests/validate_wwcx_admin_electrum_module.py
php -l deploy/wwcx-admin-electrum/templates/electrum.php
php -l deploy/wwcx-admin-electrum/templates/api/electrum-status.php
```

Live validation after installation:

1. Sign in as an administrator and open `/admin/electrum.php`.
2. Confirm the page reports balances and wallet state.
3. Confirm an unauthenticated request to `/admin/api/electrum-status.php` is rejected by the existing authorization layer.
4. Inspect browser network responses and verify no bearer token, RPC credential, wallet path, seed, or private key appears.
5. Temporarily make the upstream unavailable and verify the page shows a bounded generic error without disclosing infrastructure details.

## Rollback

Remove the navigation link and restore or remove the two target files. Remove the website-side secret file only after confirming no other component uses it. No wallet or Edge1 service state is changed by this module.
