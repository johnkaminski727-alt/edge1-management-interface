# WW.CX Authenticated Outbound-Mail Preparation API — 2026-08-01

## Purpose

This foundation provides a future server-to-server preparation path for the authenticated WW.CX website administration area, approved applications, and controlled ChatGPT-assisted workflows.

It is limited to message preparation. It can validate a request, select the canonical sender identity, generate the controlled footer and headers, and append a metadata-only preparation event. It cannot authorize or perform SMTP, Gmail API, Microsoft Graph, webhook, or other external delivery.

## Endpoints

The existing loopback browser console remains available through its local routes. External clients use separate authenticated routes:

```text
GET  /outbound-mail/api/v1/status
POST /outbound-mail/api/v1/prepare
```

The API is disabled in committed configuration. A reverse proxy, runtime secret, and explicit preparation-API activation are all deferred.

## Authentication

Requests use HMAC-SHA256 with these headers:

```text
X-WWCX-Client-ID
X-WWCX-Timestamp
X-WWCX-Nonce
X-WWCX-Content-SHA256
X-WWCX-Signature
```

The signature covers:

1. protocol marker;
2. uppercase HTTP method;
3. exact API path;
4. registered client ID;
5. Unix timestamp;
6. opaque nonce;
7. SHA-256 of the exact request body bytes.

The secret is loaded only from the environment variable named by configuration. The value is never committed, returned in status, or written to audit records.

## Replay protection

A successful authentication claims the `(client_id, nonce)` pair in a restricted SQLite store. Reuse within the configured nonce lifetime is rejected. Timestamp skew is bounded independently.

Signature and content validation occur before the nonce is claimed, so malformed requests do not consume valid nonces.

## Audit boundary

Successful API preparations append a sanitized event containing control references, hashes, selected sender, selection reason, recipient count, client ID, and `prepared_not_sent` status. The complete message body and raw action token are excluded.

## Committed safe state

```text
preparation_api.enabled = false
outbound gateway enabled = false
external delivery authorized = false
send endpoint enabled = false
all sender profiles live-enabled = false
```

The preparation API gate is separate from the live-delivery gate. Enabling preparation in the future must not imply permission to send.

## Deferred production work

The following require separate authorization and live validation:

- generating and installing the HMAC secret;
- enabling the external preparation client;
- configuring an authenticated TLS reverse proxy;
- firewall or DNS changes;
- deploying the service;
- enabling the WW.CX website bridge;
- public action-link handling;
- provider credentials or mail submission;
- production traffic cutover.
