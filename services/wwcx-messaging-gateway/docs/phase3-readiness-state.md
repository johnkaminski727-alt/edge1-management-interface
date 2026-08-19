# Phase 3 readiness state

Date: 2026-08-19

## Repository-confirmed

The carrier-neutral Phase 3 repository foundation includes durable inbound and outbound persistence, replay/idempotency controls, STOP/START/HELP consent/suppression state, outbound authorization and volume policy, destination restrictions, fail-closed MMS quarantine, bounded simulator-only workers, provider-neutral adapter interfaces, durable verified webhook receipts and recovery, webhook payload-collision rejection, bounded webhook boundary audit counters, asynchronous delivery-status reconciliation, and fail-closed uncertain-send handling.

Exact-head CI was required before every Phase 3 merge. The merged increments through readiness reconciliation passed repository validation, Messaging unit tests, and PostgreSQL/Docker integration smoke on their exact PR heads.

The final reviewed Phase 3 source state used for live deployment is commit `c4f2f1f7d63e82c613186455ca7096ba1401034d`, tree `f1539ee8938d0d657955cdaae9bed7071d032e42`, corresponding to the final PR #440 repository tree. Runtime application version is `0.4.7`.

No real carrier adapter is registered. No carrier credentials, DID, billing, public webhook, production authentication change, production telephony routing, or live SMS/MMS traffic is authorized by repository or live runtime state.

## Live Edge1 verification complete

Authenticated operator-assisted live acceptance on `edge1.ww.cx` completed successfully after the earlier PR #437-era staging pass and host-capacity remediation.

Final verified live state:

- `wwcx-messaging-gateway.service` active;
- isolated runtime at `/opt/wwcx-messaging-gateway-staging`;
- health endpoint returned `{"status":"ok"}`;
- readiness returned `{"status":"ready","storage":"postgres"}`;
- Messaging listener remained loopback-only on `127.0.0.1:58080`;
- PostgreSQL migrations `0001` through `0008` are present;
- migrations `0007_delivery_status.sql` and `0008_webhook_collision_audit.sql` were applied successfully;
- runtime role `wwadmin` has required bounded table privileges and still lacks schema-creation privilege;
- exact runtime application and migration trees match the reviewed source target;
- simulator is the only registered provider;
- inbound worker remains disabled;
- outbound worker remains disabled;
- delivery reconciliation worker remains disabled outside bounded acceptance;
- management mutation controls remain disabled;
- simulator outbound remains disabled;
- outbound policy remains disabled in persistent runtime;
- no carrier/public traffic was enabled.

## Live bounded synthetic acceptance

The final PostgreSQL-backed private acceptance pass verified:

- durable verified webhook receipt persistence and recovery;
- duplicate webhook idempotency;
- changed-body reuse of an existing provider event ID is rejected as a collision;
- bounded webhook boundary audit counters record payload conflict, verification failure, and unknown-provider outcomes without retaining raw unverified request bodies;
- `STOP` creates keyword suppression;
- `HELP` is audited without removing suppression;
- `START` removes keyword-derived suppression;
- `START` preserves unrelated/manual suppression;
- stale/out-of-order `STOP` cannot overwrite a newer `START` consent state;
- asynchronous delivery-status/DLR reconciliation applies a newer final status;
- duplicate DLR callbacks are idempotent;
- stale/out-of-order DLR events do not overwrite newer state;
- read-only management surfaces remain durable and non-mutating.

Synthetic acceptance records were cleaned after verification. Bounded aggregate webhook-audit counters were retained because removing aggregate counters could erase legitimate pre-existing audit history.

## Resource-capacity remediation

During the earlier deployment resource gate, Edge1 was found under material RAM/swap pressure. The incident was resolved before final acceptance by preserving the existing 1 GiB `/swapfile` and adding a lower-priority 2 GiB `/swapfile2`, for approximately 3 GiB total swap capacity. See `docs/operations/edge1-memory-swap-capacity-event-20260819.md`.

At final acceptance the host reported approximately 3.8 GiB RAM with about 1.5 GiB available, approximately 803 MiB swap used, and approximately 2.2 GiB swap free. `/swapfile2` remained unused reserve capacity at the sample point.

## Evidence and rollback

Durable Edge1 rollback/evidence root:

`/var/backups/wwcx-messaging-gateway/phase3-final-20260819T010540Z`

Final acceptance evidence:

`/var/backups/wwcx-messaging-gateway/phase3-final-20260819T010540Z/evidence/final-acceptance`

The earlier database/runtime backup remains retained. No destructive schema rollback was performed.

A detailed live acceptance record is maintained at `docs/communications/unified-communications-messaging-phase3-live-acceptance-20260819.md`.

## Phase 3 status

Phase 3 carrier-neutral Messaging foundation is complete at both repository-validation and private live-acceptance levels.

Carrier/public activation is not part of this completion and remains a separate authorization boundary.

## Boundaries requiring a later decision or authorization

1. Select a carrier before writing or activating a carrier-specific adapter; keep any first implementation unregistered and credential-free until signature/replay/send/delivery mapping tests pass.
2. Approve any authentication/security-policy design before creating a non-simulator enqueue identity/provenance binding.
3. Obtain carrier pricing before defining a monetary spend ceiling; current volume ceilings remain the fail-closed pre-carrier safeguard.
4. Approve the private monitoring/notification destination before wiring active alerts.
5. Separately authorize carrier activation, credentials, DIDs, public webhooks, certificates, DNS/firewall changes, production telephony routing, carrier test traffic, and production traffic cutover.
