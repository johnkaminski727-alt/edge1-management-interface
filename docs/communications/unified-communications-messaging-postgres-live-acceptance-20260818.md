# Unified Communications — Messaging PostgreSQL Live Acceptance

Date: 2026-08-18
Host: `edge1.ww.cx`
Execution path: operator-run authenticated SSH as `wwadmin`
Scope: durable private Messaging Gateway state only; no carrier traffic or provider activation

## Accepted result

Phase 18 activated the repository's existing PostgreSQL persistence path for `wwcx-messaging-gateway.service` and removed volatile in-memory storage as a runtime blocker.

PASS evidence:

- pre-activation `/readyz` reported `storage: memory` and the in-memory event count was zero;
- exact repository source baseline `7b959ebc0a3986673203a75d736b63596e3a4ddc` matched the live Messaging runtime files before activation;
- PostgreSQL 15.19 was installed only after package autostart was blocked;
- the generated `15/main` cluster was verified down before hardening;
- PostgreSQL was configured for Unix-socket-only operation with `listen_addresses = ''`;
- low-memory settings included `max_connections = 12`, `shared_buffers = 32MB`, `work_mem = 1MB`, `maintenance_work_mem = 16MB`, and `jit = off`;
- no PostgreSQL TCP listener existed after startup;
- the Unix socket `/var/run/postgresql/.s.PGSQL.5432` was present;
- a non-superuser PostgreSQL role matching the existing `wwadmin` OS identity was created for peer-authenticated local access;
- database `wwcx_messaging` was created and the exact repository migrations `0001_initial.sql` and `0002_control_state.sql` were applied;
- the resulting schema included `messaging_events`, `messages`, `message_media`, `suppressions`, `outbound_jobs`, `messaging_control_state`, and `messaging_control_audit`;
- the existing `PostgresEventStore` passed `ping()`, zero-event count, and initialized control-state checks as `wwadmin` over the Unix socket;
- a second state-loss gate confirmed the live in-memory event count was still zero immediately before restart;
- `DATABASE_URL` was configured as a local Unix-socket DSN with no password;
- only `wwcx-messaging-gateway.service` was restarted for the storage switch;
- post-restart `/readyz` returned `status: ready` and `storage: postgres`;
- HTTP event count and database event count both returned zero and matched;
- PostgreSQL was enabled for reboot persistence only after functional acceptance;
- PostgreSQL, Messaging Gateway, Communications workspace, Relay, BigBird, outbound Mail gateway, Asterisk, Kamailio, and Suricata all remained active;
- post-activation memory remained about 1.5 GiB available and no new OOM activity was observed;
- no SMS/MMS, provider/carrier routing, public listener, database password, or credential disclosure occurred.

## Security and authority boundaries

This acceptance grants no Messaging transmission authority. `messages.status.read`, `messages.conversation.read`, and prepared-not-sent drafting retain their previously accepted non-mutation boundaries. PostgreSQL is not publicly exposed and is not bound to TCP. MMS quarantine release remains unauthorized.

The MMS fail-closed metadata foundation remains live but trusted scanner and private quarantine storage are still incomplete; durable message storage does not imply MMS security readiness.

## Rollback

Rollback retained at:

`/tmp/edge1-uc-evidence-20260818T073658Z/rollback-messaging-postgres-20260818T111017Z.sh`

The rollback restores the previous Messaging Gateway environment file and restarts the gateway back on memory storage, then stops the PostgreSQL cluster and leaves its installed packages/data preserved for audit/recovery rather than destructively removing them.

## Resource note

The host remains under sustained swap pressure. Phase 18 finished with roughly 1.5 GiB `MemAvailable` and only a few hundred KiB free in the configured 1 GiB swap allocation. This did not produce new OOM evidence during activation, but broad unrelated service restarts remain undesirable.

## Readiness interpretation

Messaging Gateway durable state is now `runtime_ready`. This does not change global `fresh_edge1_runtime_verified`, which remains false until the remaining safe-scope blockers are resolved or explicitly dispositioned:

- trusted MMS scanner and private quarantine storage;
- authoritative Mail Room correspondence/thread source for `mail.correspondence.read`;
- fresh functional Voice/SIP acceptance if required for the final global flag.
