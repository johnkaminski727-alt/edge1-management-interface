# WW.CX Admin Electrum Console Module

## Purpose

Add a read-only Electrum wallet-status module to the WW.CX website administration console without exposing Electrum RPC credentials or the Edge1 API bearer token to the browser.

## Security model

- Electrum RPC remains bound to loopback on Edge1.
- The Edge1 Electrum watch API remains read-only and loopback-bound.
- The browser calls a same-origin WW.CX admin endpoint.
- The WW.CX backend reaches Edge1 through an authenticated server-to-server transport.
- The Edge1 API bearer token is stored outside the web root and never rendered into HTML or JavaScript.
- No seed, private key, wallet password, signing operation, transaction construction, or broadcast function is available.

## Initial module surface

The admin page should display:

- API/service availability;
- wallet synchronization state;
- wallet type and watch-only status when reported;
- confirmed, unconfirmed, and unmatured balances;
- network/server status available from Electrum `getinfo`;
- last successful refresh time;
- a manual refresh control.

The first release is strictly read-only. Avoid a free-form RPC console because it would undermine the API allowlist.

## Existing Edge1 API

The current service exposes:

- `GET /healthz` without credentials;
- `GET /v1/wallet/info` with bearer authentication;
- `GET /v1/wallet/balance` with bearer authentication.

The service listens on `127.0.0.1:8094`. Do not make this listener public.

## Recommended WW.CX routes

- `/admin/electrum.php` — administrator-only page.
- `/admin/api/electrum-status.php` — administrator-only same-origin JSON endpoint.

Both routes must use the existing WW.CX admin authorization guard and audit-log conventions.

## Server-to-server transport

Preferred design:

1. Establish or reuse the approved private tunnel between business159 and Edge1.
2. Publish a narrowly scoped authenticated HTTPS relay on the private path, or use the existing BigBird/Edge1 operations gateway.
3. Allow only the three Electrum watch API paths.
4. Apply short connect/read timeouts, response-size limits, TLS verification, and structured audit logging.
5. Return normalized data to the admin page; never proxy arbitrary paths or methods.

Until the private transport exists, the website module can be installed in a disabled state that reports `not_configured`.

## Configuration

Store configuration outside `public_html`, for example in a protected application configuration file or environment variables:

```text
WWCX_ELECTRUM_API_BASE=https://<private-edge1-endpoint>
WWCX_ELECTRUM_API_TOKEN=<secret>
WWCX_ELECTRUM_CONNECT_TIMEOUT=3
WWCX_ELECTRUM_TOTAL_TIMEOUT=8
```

Never commit or print the token.

## Normalized status response

The WW.CX endpoint should return a stable shape such as:

```json
{
  "ok": true,
  "service": "electrum-watch",
  "checked_at": "2026-07-21T19:00:00Z",
  "wallet": {},
  "balance": {},
  "warnings": []
}
```

On failure, return a generic error code to the browser while recording detailed diagnostics only in the protected server log:

```json
{
  "ok": false,
  "error": "backend_unavailable"
}
```

## Navigation

Add an `Electrum` item under the admin console's finance, payments, or infrastructure section. Preserve the existing global navigation helper and avoid duplicating menu markup when a shared navigation registry exists.

## Audit requirements

Record:

- administrator user ID;
- action `electrum_status_view` or `electrum_status_refresh`;
- timestamp;
- success/failure;
- request correlation ID;
- no wallet secrets, tokens, addresses, xpubs, or raw backend error bodies.

## Acceptance checks

- Unauthenticated and non-admin users receive the existing access-denied behavior.
- Browser source and network responses contain no Edge1 bearer token.
- Only approved GET operations are possible.
- The page handles an unavailable Edge1 service without exposing stack traces.
- Responses use `Cache-Control: no-store`.
- The existing admin navigation and authorization validators pass.
- PHP syntax checks pass for every added or changed PHP file.
- Edge1 Electrum API and service validators continue to pass.

## Deployment boundary

Installing the website module and private transport changes production-facing administration behavior and may touch authentication or networking. Prepare and validate the code first, then apply it during an approved deployment step with rollback copies of changed website files and configuration.
