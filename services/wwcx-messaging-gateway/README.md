# WW.CX Messaging Gateway

Provider-neutral SMS/MMS gateway staged separately from FreePBX and Asterisk.

## Safety boundary

The gateway is designed so that repository implementation, runtime readiness, carrier configuration, credentials, authorization, and live traffic are separate states. Source code or an AI-generated draft is never authority to send.

The currently accepted Edge1 runtime remains private and loopback-only. No real carrier, DID, public webhook, production credential, or live SMS/MMS traffic is enabled by this repository state.

## Current carrier-neutral capabilities

- health and readiness endpoints;
- normalized inbound and outbound SMS/MMS event models;
- PostgreSQL durable event persistence;
- durable inbound and outbound queues with bounded workers;
- provider-neutral webhook and send interfaces;
- verified-webhook receipt persistence and recovery;
- provider-event replay/idempotency and changed-body collision rejection;
- bounded webhook abuse/audit counters without retaining unverified bodies;
- STOP / START / HELP consent and suppression state with ordering protection;
- outbound sender, destination, volume, recipient-count and message-length policy;
- delivery-status/DLR persistence, ordering and idempotency;
- fail-closed uncertain-send behavior to prevent duplicate delivery;
- private content-addressed MMS quarantine storage with digest verification;
- trusted-scanner adapter with fail-closed timeout/error/unavailable states;
- clean MMS remains held until a separate release policy exists;
- authenticated bounded AI conversation reads;
- prepared-not-sent AI message drafting;
- simulator-only private acceptance paths.

## Carrier adapter state

`app/telnyx_provider.py` is the first real-carrier reference implementation. It provides:

- Ed25519 webhook verification using Telnyx signature and timestamp headers;
- five-minute replay-window enforcement;
- inbound SMS/MMS normalization;
- terminal delivery-status normalization;
- credential-injected outbound submission;
- explicit separation between permanent provider rejection, proven safe retry, and outcome-uncertain submission.

The Telnyx adapter is deliberately **not registered** by `build_provider_registry()`. The simulator remains the only active provider. Adding source code does not activate Telnyx, install credentials, expose a webhook, assign a telephone number, or authorize traffic.

Commercial carrier selection and activation remain separate approval decisions. Current pricing, regulatory requirements, number availability and contractual terms must be revalidated before any purchase or activation.

## MMS private quarantine

MMS provider references are untrusted. The private quarantine store uses content-addressed paths derived from SHA-256 rather than provider-controlled filenames or URLs, enforces private filesystem permissions and bounded size limits, and verifies stored bytes against the expected digest. Scan adapters operate on verified private blobs. Scanner failure, timeout, absence, unknown verdict, metadata corruption or digest failure all hold the attachment.

A clean scan produces `scanned_clean_held`; it does not authorize release. The ordinary AI/read surface does not expose provider media URLs.

## AI boundary

BigBird may read bounded sanitized messaging context and prepare drafts. Retrieved SMS/MMS content is explicitly untrusted data and cannot grant scopes, authorize tools, change policy, reveal secrets, release quarantine, or authorize delivery.

Repository/live capabilities currently include:

- `messaging.status.read`
- `messages.conversation.read`
- `messages.draft.prepare`

`messages.draft.prepare` produces a local `prepared_not_sent` artifact. No `messages.send` authority is granted by this integration.

## Outbound lifecycle

The durable queue and worker preserve a fail-closed progression. Before a worker can call a provider, the job must pass provider allowlisting, provider registration, outbound policy, sender/destination restrictions, suppression, MMS-release restrictions and rate controls.

Provider outcomes are treated conservatively:

- proven pre-submit connection failure may be retried;
- explicit provider rejection is blocked for operator review;
- ambiguous submission failure remains claimed and requires reconciliation;
- accepted submission records the provider message ID for later DLR reconciliation.

The worker still runs one bounded iteration only and is disabled unless explicitly enabled.

## Local development

```bash
cd services/wwcx-messaging-gateway
python -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
export WWCX_SIMULATOR_TOKEN=development-only
uvicorn app.main:app --reload --port 8092
```

Run validation:

```bash
pytest -q
python -m compileall app tests
```

PostgreSQL/Docker integration acceptance is exercised by the repository `WW.CX Messaging Gateway` workflow.

## Live private acceptance baseline

The last documented carrier-neutral Edge1 acceptance uses application version `0.4.7`, PostgreSQL, loopback listener `127.0.0.1:58080`, simulator-only provider registration, disabled outbound/inbound workers in persistent runtime, disabled outbound policy, and no public carrier traffic. See `docs/phase3-readiness-state.md` for exact evidence and rollback locations.

## Remaining activation boundaries

The following are intentionally not implied by this README or by a green CI run: carrier commercial acceptance, charges, telephone-number purchase/assignment, carrier credentials, externally reachable production webhooks, production DNS/firewall/certificate changes, live SMS/MMS test traffic, production traffic cutover, credential rotation, or legal/regulatory representations.
