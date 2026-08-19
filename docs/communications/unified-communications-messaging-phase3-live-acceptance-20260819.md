# WW.CX Messaging Gateway Phase 3 live acceptance

Date: 2026-08-19
Host: `edge1.ww.cx`
Service: `wwcx-messaging-gateway.service`
Runtime: `/opt/wwcx-messaging-gateway-staging`
Reviewed Phase 3 source commit: `c4f2f1f7d63e82c613186455ca7096ba1401034d`
Reviewed Phase 3 source tree: `f1539ee8938d0d657955cdaae9bed7071d032e42`
Runtime application version: `0.4.7`

## Result

Phase 3 private live acceptance completed successfully in an authenticated operator-assisted Edge1 session.

The final runtime remains private, loopback-only, simulator-only, and fail-closed. This acceptance does not authorize or imply carrier activation, public webhook exposure, live SMS/MMS traffic, DID provisioning, billing, DNS/firewall/TLS/authentication changes, or production telephony routing.

## Deployment state

Verified after finalization:

- PostgreSQL migrations `0001` through `0008` are present;
- migrations `0007_delivery_status.sql` and `0008_webhook_collision_audit.sql` were applied successfully;
- database objects are owned under the existing PostgreSQL ownership model;
- runtime role `wwadmin` has the required bounded table privileges and still lacks `CREATE` on schema `public`;
- exact Messaging application and migration trees match the reviewed source target;
- provider registry contains only `simulator`;
- health returned `{"status":"ok"}`;
- readiness returned `{"status":"ready","storage":"postgres"}`;
- service remained active;
- listener remained `127.0.0.1:58080` only.

## Bounded synthetic acceptance

The following live local/simulator checks passed against PostgreSQL-backed runtime state:

- verified webhook receipt persistence;
- duplicate webhook idempotency;
- changed-body reuse of an existing provider event ID returns collision rejection;
- bounded webhook boundary audit counters record payload conflict, verification failure, and unknown-provider outcomes without retaining raw unverified request bodies;
- `STOP` establishes keyword suppression;
- `HELP` is audited without removing suppression;
- `START` removes keyword-derived suppression;
- `START` preserves unrelated/manual suppression;
- stale/out-of-order `STOP` cannot overwrite a newer `START` consent state;
- durable verified webhook receipt recovery succeeds;
- asynchronous delivery-status/DLR reconciliation applies a newer final status;
- duplicate DLR callbacks are idempotent;
- stale/out-of-order DLR events do not overwrite newer state;
- read-only management surfaces remain durable and non-mutating.

Synthetic acceptance records were cleaned after verification. Bounded aggregate webhook audit counters were intentionally preserved because removing aggregate counters could erase legitimate pre-existing audit history.

## Final fail-closed gates

Verified after acceptance:

- `WWCX_SIMULATOR_OUTBOUND_ENABLED` disabled;
- `WWCX_MANAGEMENT_CONTROL_ENABLED` disabled;
- `WWCX_INBOUND_WORKER_ENABLED` disabled;
- `WWCX_OUTBOUND_WORKER_ENABLED` disabled;
- `WWCX_DELIVERY_RECONCILE_ENABLED` disabled;
- `WWCX_OUTBOUND_POLICY_ENABLED` disabled;
- outbound provider allowlist restricted to `simulator`;
- no real carrier adapter registered;
- no public webhook exposed;
- no external SMS/MMS sent.

## Resource-capacity incident and remediation

During the earlier Phase 3 deployment acceptance, Edge1 was found under real RAM/swap pressure. That operational incident was resolved before final acceptance by preserving the existing 1 GiB `/swapfile` and adding a lower-priority 2 GiB `/swapfile2`, providing approximately 3 GiB total swap capacity. The incident is documented in `docs/operations/edge1-memory-swap-capacity-event-20260819.md`.

At final acceptance the host reported approximately 3.8 GiB RAM with about 1.5 GiB available, approximately 803 MiB swap in use, and approximately 2.2 GiB swap free. `/swapfile2` remained unused reserve capacity at the sample point.

## Evidence and rollback

Durable Edge1 evidence and rollback root:

`/var/backups/wwcx-messaging-gateway/phase3-final-20260819T010540Z`

Final acceptance evidence:

`/var/backups/wwcx-messaging-gateway/phase3-final-20260819T010540Z/evidence/final-acceptance`

The prior database/runtime backup was retained. No destructive schema rollback was performed.

## Phase 3 conclusion

The carrier-neutral Messaging Phase 3 foundation is now both repository-validated and live-verified on the private Edge1 simulator-only runtime.

Future carrier/public activation remains a separate authorization boundary.
