# Outbound mail Phase B — authenticated preparation API

Date: 2026-08-01

## Objective

Enable authenticated `prepared_not_sent` requests without enabling any mail provider, sender identity, SMTP/API delivery path, public correspondence record, or message traffic.

Phase B is deliberately split:

- **B1 — loopback authenticated preparation:** install a runtime configuration overlay and root-owned HMAC secret for the existing `127.0.0.1:8104` service.
- **B2 — TLS reverse proxy:** expose only the two authenticated preparation API routes after separate certificate, hostname, network-source, and proxy authorization.

B1 does not install or alter a reverse proxy. B2 must not be combined with B1 implicitly.

## Committed safe state

The repository configuration remains disabled:

- `enabled=false`;
- `external_delivery_authorized=false`;
- `admin.send_endpoint_enabled=false`;
- `preparation_api.enabled=false`;
- provider selection `none` and every provider disabled;
- policy delivery and SMTP cutover disabled;
- global outbound identity activation and every sender disabled.

B1 creates `/etc/wwcx/outbound-mail-gateway.json` from the committed configuration and changes only `preparation_api.enabled` in that runtime copy. It never edits the Git working tree.

## Runtime files

B1 uses:

- `/etc/wwcx/outbound-mail-gateway.json` — non-secret runtime configuration;
- `/etc/wwcx/outbound-mail-gateway.env` — root-owned `0600` environment file containing only `WWCX_MAIL_GATEWAY_TOKEN`;
- `/etc/systemd/system/wwcx-outbound-mail-gateway.service.d/20-preparation-api.conf` — service drop-in selecting the runtime configuration and environment file;
- `/opt/edge1-management-interface/var/outbound-mail/preparation-nonces.sqlite3` — replay-protection state;
- `/opt/edge1-management-interface/var/outbound-mail/audit.jsonl` — sanitized preparation audit records.

The secret is not accepted as a command-line value, written to the repository, copied into evidence, printed, hashed into the evidence bundle, or returned by status endpoints.

## B1 prerequisites

Before a live B1 action:

1. Phase A service is active and healthy on loopback port 8104.
2. Repository is on clean `main` at the separately approved commit.
3. A dedicated secret-generation action has been explicitly authorized.
4. The secret is at least 43 URL-safe characters and stored in a root-owned regular file with mode `0400` or `0600`.
5. No reverse proxy, DNS, firewall, or certificate action is included.

A suitable secret may be generated only after authorization with a cryptographically secure generator. Do not paste it into chat, a shell command argument, GitHub, issue comments, logs, or a shared document.

## B1 installation

The operator supplies the path to the already-created secret file:

```sh
cd /opt/edge1-management-interface

git fetch --prune origin main
git pull --ff-only origin main

APPROVED_COMMIT=$(git rev-parse HEAD)

sudo EXPECTED_COMMIT="$APPROVED_COMMIT" \
  SECRET_SOURCE_FILE=/root/wwcx-mail-gateway-token \
  sh deploy/messaging/install-outbound-mail-preparation-api.sh
```

The installer refuses:

- non-root execution;
- non-`main` or dirty source;
- an unexpected commit;
- an inactive Phase A service;
- an absent, symlinked, non-root-owned, broadly readable, malformed, or undersized secret file;
- any committed provider, delivery, sender, or preparation activation state that is already unsafe.

It backs up pre-existing runtime files, installs the runtime overlay, restarts the service, runs the signed canary, and automatically restores the prior state if any verification fails.

## B1 canary contract

`tools/outbound_mail_preparation_canary.py` is loopback-restricted and verifies:

- unsigned authenticated-status request returns `401 authentication_failed`;
- correctly signed status returns HTTP 200;
- the preparation gate and runtime secret are active;
- signed preparation returns `prepared_not_sent`;
- canonical sender selection resolves to the requested registered identity;
- the selected sender remains live-disabled;
- reuse of the same nonce returns `409 replay_detected`;
- `/outbound-mail/send` remains `403 delivery_disabled`;
- no provider is ready and no live sender exists.

The repository validator also confirms that neither the secret nor the synthetic body appears in the audit record and that no raw action token is stored. The permitted `action_token_sha256` value must be a 64-character lowercase SHA-256 digest.

## B1 rollback or disable

The following removes the runtime overlay and restores the committed Phase A disabled service:

```sh
cd /opt/edge1-management-interface
APPROVED_COMMIT=$(git rev-parse HEAD)

sudo ACTION=disable EXPECTED_COMMIT="$APPROVED_COMMIT" \
  sh deploy/messaging/install-outbound-mail-preparation-api.sh
```

The disable path restarts the service and executes the original Phase A smoke test, which requires preparation and delivery to be disabled.

## Evidence

B1 writes a restricted evidence directory under:

`/var/lib/wwcx-deployment-evidence/outbound-mail-phase-b1/<UTC timestamp>/`

Evidence includes:

- host, principal, branch, commit, action, and secret length only;
- before/after service properties and listener inventory;
- sanitized runtime configuration and source hashes;
- signed canary result;
- sanitized status and journal output;
- SHA-256 inventory.

The secret file and installed environment file are never copied into evidence.

The current committed audit policy explicitly sets `record_recipient_addresses=true`. Accordingly, the preparation audit JSONL retains recipient addresses as correspondence metadata. It does not retain message bodies or raw action tokens; the action token is represented only by its SHA-256 digest. Changing recipient-address retention is a separate records-policy decision and is not bundled into Phase B activation.

## B2 staged TLS proxy contract

`deploy/messaging/outbound-mail-preparation-api-nginx.conf.example` is a non-deployable template. It contains placeholders for:

- approved API hostname;
- certificate and private-key paths;
- smallest possible client source CIDR.

The template exposes exactly:

- `GET /outbound-mail/api/v1/status`;
- `POST /outbound-mail/api/v1/prepare`.

Every other path returns 404. It forwards to `127.0.0.1:8104`, disables redirects, does not forward an originating IP chain, limits request size, and requires TLS 1.2 or 1.3. HMAC remains mandatory at the application layer.

B2 requires separate authorization for the exact hostname, certificate, reverse-proxy configuration, source network, firewall implications, and external canary. The template must not be installed as-is.

## Stop conditions

Stop before:

- generating or rotating the secret;
- installing B1 runtime authentication material;
- installing a certificate or reverse proxy;
- changing DNS or firewall rules;
- enabling website external preparation;
- activating public correspondence records or retention apply;
- selecting a delivery provider or enabling any sender;
- sending any production message.
