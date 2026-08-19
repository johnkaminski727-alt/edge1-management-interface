# Phase 3 readiness state

Date: 2026-08-19

## Repository-confirmed

The carrier-neutral Phase 3 repository foundation includes durable inbound and outbound persistence, replay/idempotency controls, STOP/START/HELP consent/suppression state, outbound authorization and volume policy, destination restrictions, fail-closed MMS quarantine, bounded simulator-only workers, provider-neutral adapter interfaces, durable verified webhook receipts and recovery, webhook payload-collision rejection, bounded webhook boundary audit counters, asynchronous delivery-status reconciliation, and fail-closed uncertain-send handling.

Exact-head CI is required before every merge. The merged Phase 3 increments through webhook collision/audit have passed repository validation, messaging unit tests, and PostgreSQL/Docker integration smoke on their exact PR heads.

No real carrier adapter is registered. No carrier credentials, DID, billing, public webhook, production authentication change, production telephony routing, or live SMS/MMS traffic is authorized by repository state.

## Not live-verified in this session

Live Edge1 acceptance is intentionally not claimed. The expected automatic `edge1.identity`, `edge1.health`, `edge1.snapshot`, `edge1.services`, `edge1.messaging_status`, `edge1.git_state`, and `edge1.config_digest` tool surface was not exposed to this ChatGPT session, and no installable Edge1 Operator plugin was discoverable through plugin management.

Accordingly, this session did not mutate or claim verification of the live Edge1 checkout, services, listeners, PostgreSQL migration level, runtime configuration, worker state, backup/restore state, or rollback state.

When the live Edge1 tool surface is restored, use the private staging and rollback runbook to capture the pre-change snapshot, back up affected state, apply the reviewed migrations/runtime without broadening listeners, verify simulator-only provider registration and disabled workers, run bounded private acceptance, capture post-apply evidence, and prove rollback/restore.

## Boundaries requiring a later decision or authorization

1. Select a carrier before writing a carrier-specific adapter; keep the first implementation unregistered and credential-free until signature/replay/send/delivery mapping tests pass.
2. Approve any authentication/security-policy design before creating a non-simulator enqueue identity/provenance binding.
3. Obtain carrier pricing before defining a monetary spend ceiling; current volume ceilings remain the fail-closed pre-carrier safeguard.
4. Approve the private monitoring/notification destination before wiring active alerts.
5. Separately authorize carrier activation, credentials, DIDs, public webhooks, certificates, DNS/firewall changes, production telephony routing, carrier test traffic, and production traffic cutover.
