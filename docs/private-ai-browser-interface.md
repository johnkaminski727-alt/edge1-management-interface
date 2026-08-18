# WW.CX Private AI browser interface

Date: 2026-08-18

## Objective

Provide a normal authenticated browser path for the accepted Edge1 Private AI gateway without exposing the gateway listener or signing material.

User-facing URL after website deployment:

`https://ww.cx/admin/bigbird-ai-chat.php`

The Edge1 gateway remains:

`http://127.0.0.1:8787`

## Trust boundary

```text
Browser
  |
  | existing WW.CX admin session + same-origin CSRF
  v
ww.cx /admin/bigbird-ai-chat.php
  |
  | private queue; no gateway secret in browser
  v
ww.cx /api/bigbird-ai-worker.php
  ^
  | signed HTTPS pull/complete requests
  |
Edge1 private-ai-browser-worker.service
  |
  | existing gateway HMAC identity
  v
127.0.0.1:8787/v1/chat
```

The worker is outbound-only from Edge1 to `https://ww.cx/api/bigbird-ai-worker.php`. It does not create a new public Edge1 listener, proxy port 8787, or expose an AMI/ARI/FreePBX credential.

## Authentication and credentials

The browser reuses the existing WW.CX admin authentication and CSRF infrastructure. No new browser credential system is introduced.

The Edge1 worker reads signing material only from environment variables:

- `BB_BROWSER_WORKER_KEY_ID` and `BB_BROWSER_WORKER_SECRET` for the existing WW.CX queue worker HMAC contract;
- `BB_RELAY_KEY_ID` and `BB_RELAY_SECRET` for the accepted Private AI gateway request-signing contract.

Secret values are never command-line arguments, repository content, browser responses, source/provenance fields, or log fields.

## Browser capabilities

The browser can request these read-only contexts when the deployed gateway supports them:

- baseline `chat:general`;
- sanitized Edge1 status;
- approved private-library operations collection;
- documentation retrieval;
- Communications Relay read context with provenance;
- telephony read context, including Asterisk/FreePBX/PJSIP health and aggregate call/interconnect information.

Asterisk/FreePBX mutation is deliberately not enabled by the browser release. No call origination, trunk edit, endpoint edit, routing edit, dialplan reload, service restart, DTMF transmission, emergency-path action, AMI/ARI mutation, database query, or credential access is introduced.

## Mail and correspondence integration

Mail belongs in this same AI control surface, but with its own scopes and source boundaries.

Existing Edge1 foundations already provide:

- inbound mail-hub health/status/audit/quarantine metadata;
- an outbound correspondence preparation gateway whose accepted state is `prepared_not_sent`;
- identity-aware sender-selection and mail compliance controls.

The recommended AI increments are:

1. `mail.status.read` — expose sanitized inbound/outbound operational status and routing metadata to AI;
2. `mail.correspondence.read` — expose explicitly approved message/thread content only when a mailbox/content adapter exists and preserves private/shared mailbox boundaries;
3. `mail.draft.prepare` — allow AI to prepare a correspondence draft through the existing preparation gateway while preserving `prepared_not_sent`;
4. separately gated mutation scopes for actual send, archive, delete, unsubscribe, forwarding, or mailbox configuration actions.

No send capability should be inferred from `chat:general`, mail read scopes, or the preparation workflow.

## Edge1 worker deployment

Repository assets:

- `server/private_ai_browser_worker.py`
- `deploy/private-ai-browser-worker.service`
- `tests/test_private_ai_browser_worker.py`

Preflight on Edge1 must confirm the accepted `bigbird-ai-gateway.service`, its loopback `127.0.0.1:8787` listener, the repository checkout, and the intended `bigbird-ai` service identity.

Install the service file only after confirming `/opt/edge1-management-interface` is the live repository path. Provide the existing queue worker and gateway signing values to `/etc/wwcx/private-ai-browser-worker.env` with root/service-readable mode only. Do not print the values during deployment evidence capture.

Required non-secret environment shape:

```text
BB_BROWSER_WORKER_KEY_ID=<existing queue worker key id>
BB_BROWSER_WORKER_SECRET=<existing queue worker secret>
BB_RELAY_KEY_ID=<existing Private AI gateway key id>
BB_RELAY_SECRET=<existing Private AI gateway secret>
BB_BROWSER_QUEUE_URL=https://ww.cx/api/bigbird-ai-worker.php
BB_BROWSER_GATEWAY_URL=http://127.0.0.1:8787/v1/chat
```

Validate the service unit and repository tests before enabling it. After start, verify that no new public listener appears and that port 8787 remains loopback-only.

## Website deployment

The authoritative browser implementation is in `johnkaminski727-alt/ww-cx-website`.

Use the existing Business159 deployment procedure:

```text
~/apps/ww-cx-website/scripts/deploy-business159.sh --dry-run
~/apps/ww-cx-website/scripts/deploy-business159.sh
```

Deployment remains from reviewed `origin/main`; the live document root is not the source of truth.

## Acceptance

The browser milestone is complete only when all of the following are verified:

1. `https://ww.cx/admin/bigbird-ai-chat.php` requires the existing WW.CX administrator session;
2. unauthenticated queue requests fail closed;
3. CSRF rejection remains active;
4. a browser request enters the private queue;
5. Edge1 claims it through signed HTTPS;
6. Edge1 signs and sends it only to `127.0.0.1:8787/v1/chat`;
7. the result returns through the signed queue completion path;
8. source/provenance fields render safely in the browser;
9. Communications, documentation and telephony remain opt-in/read-only;
10. no secret reaches browser JavaScript or response data;
11. no new Edge1 public listener appears;
12. Asterisk/FreePBX and mail mutations remain disabled unless separately authorized.

## Rollback

Disable and stop only `private-ai-browser-worker.service`, preserving its logs and queue evidence. Restore the prior WW.CX website release with the existing Business159 rollback procedure. Do not alter the accepted `bigbird-ai-gateway.service`, its port 8787 binding, firewall, DNS, TLS, PBX routing, mail routing, or credentials as part of browser rollback.
