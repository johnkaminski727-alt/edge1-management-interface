# Phase 3 readiness state

Date: 2026-08-19

## Repository-confirmed

The carrier-neutral Phase 3 repository foundation includes durable inbound and outbound persistence, replay/idempotency controls, STOP/START/HELP consent/suppression state, outbound authorization and volume policy, destination restrictions, fail-closed MMS quarantine, bounded simulator-only workers, provider-neutral adapter interfaces, durable verified webhook receipts and recovery, webhook payload-collision rejection, bounded webhook boundary audit counters, asynchronous delivery-status reconciliation, and fail-closed uncertain-send handling.

Exact-head CI is required before every merge. The merged Phase 3 increments through readiness reconciliation passed repository validation, messaging unit tests, and PostgreSQL/Docker integration smoke on their exact PR heads.

The final reviewed repository state is commit `dc103f013ca6e95f1b10a16070591f6d8f93c889` (PR #440 merge), including the review follow-ups for delivery/DLR reconciliation, webhook boundary audit and payload-collision handling, uncertain-send reconciliation, durable inbound receipt recovery, and repository-versus-live readiness reconciliation.

No real carrier adapter is registered. No carrier credentials, DID, billing, public webhook, production authentication change, production telephony routing, or live SMS/MMS traffic is authorized by repository state.

## Live Edge1 verification completed in the operator-assisted session

A manual authenticated SSH operator session on `edge1.ww.cx` completed private staging through commit `3fec8df207587fc794a4751f4584fc1162b360da` (PR #437-era state).

Verified live facts at that point:

- `wwcx-messaging-gateway.service` active;
- isolated runtime at `/opt/wwcx-messaging-gateway-staging`;
- health endpoint returned `{"status":"ok"}`;
- readiness returned `{"status":"ready","storage":"postgres"}`;
- Messaging listener remained loopback-only on `127.0.0.1:58080`;
- PostgreSQL remained socket-only with no TCP listener on 5432;
- migrations `0003` through `0006` were applied as database owner `postgres`;
- runtime application role `wwadmin` retained no schema-creation privilege;
- simulator was the only registered provider;
- outbound and inbound workers remained disabled;
- no carrier/public traffic was enabled;
- durable predeployment database/runtime rollback artifacts were preserved under `/var/backups/wwcx-messaging-gateway/20260819T002603Z`.

During the post-deployment resource gate, the host was found to be under material RAM/swap pressure. That capacity event was investigated separately and remediated by preserving the existing 1 GiB swapfile and adding a lower-priority 2 GiB `/swapfile2`, for approximately 3 GiB total swap. See `docs/operations/edge1-memory-swap-capacity-event-20260819.md`.

## Live work still required

Live acceptance of the final repository state `dc103f013ca6e95f1b10a16070591f6d8f93c889` is not yet complete. The live isolated runtime was deliberately pinned to the earlier reviewed target while the database/runtime deployment and subsequent host-capacity issue were handled.

The remaining bounded work is:

1. compare the live PR #437-era runtime with the final Phase 3 repository state and review the incremental migrations/runtime changes from PRs #438-#440;
2. back up the current live runtime/database state before any additional mutation;
3. deploy only the Messaging Gateway files required to reach the final reviewed Phase 3 state, without fast-forwarding the whole shared repository;
4. keep provider registration simulator-only and both workers disabled except for an explicitly bounded synthetic one-shot acceptance;
5. run local/simulator acceptance for STOP/START/HELP, outbound authorization/rate policy, webhook idempotency/collision handling, durable receipt recovery, uncertain-send handling, and asynchronous delivery-status reconciliation;
6. capture final service, listener, database, configuration, resource, and rollback evidence;
7. keep all carrier/public activation gates closed.

## Boundaries requiring a later decision or authorization

1. Select a carrier before writing a carrier-specific adapter; keep the first implementation unregistered and credential-free until signature/replay/send/delivery mapping tests pass.
2. Approve any authentication/security-policy design before creating a non-simulator enqueue identity/provenance binding.
3. Obtain carrier pricing before defining a monetary spend ceiling; current volume ceilings remain the fail-closed pre-carrier safeguard.
4. Approve the private monitoring/notification destination before wiring active alerts.
5. Separately authorize carrier activation, credentials, DIDs, public webhooks, certificates, DNS/firewall changes, production telephony routing, carrier test traffic, and production traffic cutover.
