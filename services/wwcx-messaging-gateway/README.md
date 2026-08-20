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

The repository contains two real-carrier adapter implementations, **Telnyx and Bandwidth**, behind the same provider-neutral boundary. Both remain deliberately unregistered and credential-free in the active runtime.

`app/telnyx_provider.py` provides:

- Ed25519 webhook verification using Telnyx signature and timestamp headers;
- five-minute replay-window enforcement;
- inbound SMS/MMS normalization;
- terminal delivery-status normalization;
- credential-injected outbound submission;
- authenticated Telnyx MMS acquisition into private quarantine;
- explicit separation between permanent provider rejection, proven safe retry, and outcome-uncertain submission.

`app/bandwidth_provider.py` provides:

- Messaging-V2 callback HTTP Basic verification;
- provider-specific `WWW-Authenticate` challenge support without hard-coding Bandwidth into the shared route;
- Bandwidth JSON-array callback normalization;
- inbound SMS/MMS normalization;
- terminal `message-delivered` / `message-failed` DLR normalization;
- allowlisted Bandwidth MMS media-reference validation;
- credential-injected Messaging-V2 outbound submission;
- Bandwidth's ten-recipient outbound limit enforced before submission;
- the same fail-closed rejection, safe-retry, and outcome-uncertain semantics used by the carrier-neutral worker.

`build_provider_registry()` still registers only the simulator. Adding adapter source does not activate either carrier, install credentials, expose a webhook, assign a telephone number, or authorize traffic.

The dual-carrier policy is explicit-provider routing rather than blind failover. A sender/telephone number must remain associated with its configured carrier. A failed or outcome-uncertain submission must not be retransmitted automatically through the other carrier because the sender may not be authorized there and the first carrier may already have accepted the message.

Commercial carrier activation remains a separate approval decision. Current pricing, regulatory requirements, number availability and contractual terms must be revalidated before any purchase or activation.

## MMS private quarantine

MMS provider references are untrusted. The private quarantine store uses content-addressed paths derived from SHA-256 rather than provider-controlled filenames or URLs, enforces private filesystem permissions and bounded size limits, and verifies stored bytes against the expected digest. Scan adapters operate on verified private blobs. Scanner failure, timeout, absence, unknown verdict, metadata corruption or digest failure all hold the attachment.

Telnyx authenticated media acquisition can populate that store when verified provider metadata includes an expected digest. Bandwidth callback media references currently arrive without an authoritative digest in this adapter and therefore remain held by the existing fail-closed quarantine policy until a separately verified acquisition/digest path is implemented.

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
