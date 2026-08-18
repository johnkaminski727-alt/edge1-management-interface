# Unified Communications — Validation Record

Date: 2026-08-18
Scope: repository-side completion, CI evidence, and fresh authenticated Edge1 operator acceptance
Global fresh runtime completion: partial; Relay canonical feed, persistent workspace, and durable Messaging PostgreSQL state are accepted, while MMS scanner/storage, Mail correspondence, and any required fresh Voice/SIP acceptance remain incomplete

## Accepted merged increments

| PR | Increment | Final head / merge evidence | CI result |
|---|---|---|---|
| #384 | Canonical event / identity / readiness / correlation core | merge `6b272fb0308bfeb161f50598845fc88b77e5c561` | PASS |
| #385 | SMS/MMS Private AI read + draft | merge `ce5c561304a0a7aa109b887d1739ae90660b7633` | PASS |
| #386 | Mail Room AI status + draft | merge `9e26ea6df6e0bc3469d3bc63701362b01a80bd94` | PASS |
| #387 | Unified Communications workspace | merge `2b4550812cb6bc790cb3b3bc0d079bdfd261b220` | PASS |
| #389 | MMS media quarantine foundation | merge `721d5e538835a4b53a05c2208e7940f1d83ec043` | PASS |
| #396 | Final repository reconciliation | merge `d7ccf2189a028df474ce5b7931870e10d6ec4292` | PASS |
| #397 | Fresh Edge1 UC acceptance reconciliation | merge `6d2c24dfb756bbb735dabc4ffca51d9a6a8b73fc` | PASS |
| #400 | Hardened Communications workspace service deployment | merge `a46ec4433033648c3428ce061318cdaf347a3605` | PASS |
| #404 | Durable Relay canonical snapshot adapter | merge `78a4bc5563262f6da52e626a396248472b7852c7` | PASS |
| #406 | Relay snapshot service identity correction | merge `c02cb3a1751d4b32768def32682bb150e90f308b` | PASS |
| #407 | SQLite WAL/SHM sidecar sandbox correction | merge `f5cf3047965a28a23ddc249c2c2f57ea167f7da8` | PASS |
| #408 | Live Relay canonical snapshot acceptance reconciliation | merge `7b959ebc0a3986673203a75d736b63596e3a4ddc` | PASS |

## Evidence interpretation

Repository CI and operator-run Edge1 evidence are distinct. Green GitHub Actions workflows establish repository validation only. Fresh live claims below come from authenticated operator-run SSH acceptance on `edge1.ww.cx`.

The global `fresh_edge1_runtime_verified` flag remains false until the intended safe-scope runtime surfaces are complete. Fresh runtime acceptance does not imply production-traffic authorization.

## Fresh Edge1 acceptance — Messaging Gateway

PASS:

- live `wwcx-messaging-gateway.service` version `0.4.2`;
- health/readiness on loopback `127.0.0.1:58080`;
- authenticated `messages.status.read` and `messages.conversation.read`;
- recent conversation contract `wwcx.messages-conversation-read.v1`;
- untrusted-content marker and `mutation_authorized: false`;
- fail-closed MMS quarantine projection with `release_authorized: false`;
- no SMS/MMS traffic generated.

### Phase 18 durable PostgreSQL acceptance

PASS:

- pre-activation `/readyz` reported `storage: memory` and simulator event count was zero;
- exact merged source baseline `7b959ebc0a3986673203a75d736b63596e3a4ddc` matched the live Messaging runtime before activation;
- PostgreSQL 15.19 installation used `policy-rc.d` to prevent package autostart before hardening;
- new `15/main` cluster was confirmed down before configuration;
- PostgreSQL configured local-only with `listen_addresses = ''`;
- low-memory configuration set `max_connections=12`, `shared_buffers=32MB`, `work_mem=1MB`, `maintenance_work_mem=16MB`, and `jit=off`;
- PostgreSQL started with only Unix socket `/var/run/postgresql/.s.PGSQL.5432`; no TCP listener existed;
- least-privilege non-superuser PostgreSQL role `wwadmin` created for peer-authenticated local use;
- database `wwcx_messaging` created and exact repository migrations `0001_initial.sql` and `0002_control_state.sql` applied;
- resulting schema contained Messaging event/message/media/suppression/outbound/control/audit tables;
- local `PostgresEventStore` smoke test passed ping, zero count, and initialized control state;
- a second zero-event state-loss gate passed immediately before restart;
- `DATABASE_URL` configured as a Unix-socket DSN with no database password;
- only `wwcx-messaging-gateway.service` restarted for the storage switch;
- post-restart `/readyz` returned `storage: postgres`;
- live HTTP event count and PostgreSQL event count both returned zero;
- PostgreSQL enabled for reboot persistence only after functional validation;
- PostgreSQL, Messaging Gateway, Communications workspace, Relay, BigBird, outbound Mail, Asterisk, Kamailio, and Suricata remained active;
- post-activation `MemAvailable` remained approximately 1.5 GiB and no new OOM evidence was observed;
- no SMS/MMS, provider routing, public database listener, database password, or credentials were generated or changed.

Rollback:

`/tmp/edge1-uc-evidence-20260818T073658Z/rollback-messaging-postgres-20260818T111017Z.sh`

Messaging durability is now freshly `runtime_ready` and no longer a blocker.

## Fresh Edge1 acceptance — BigBird

PASS:

- live BigBird version `0.3.4-alpha.3` in read-only mode;
- eight registry tools including `messages.conversation.read` and `messages.draft.prepare`;
- explicit-scope authorization and missing-scope rejection;
- live conversation read and local prepared-not-sent draft preparation;
- `send_authorized: false` and `mutation_authorized: false` preserved;
- messaging control remained disabled;
- unsigned `/v1/chat` returned HTTP `401`;
- no production communications traffic generated.

## Fresh Edge1 acceptance — Mail AI adapter

PASS for local bounded adapter behavior:

- `mail.status.read`;
- `mail.draft.prepare`;
- prepared-not-sent semantics;
- no send/mutation authority.

Still blocked: `mail.correspondence.read` pending an explicitly authorized authoritative native Mail Room correspondence source.

## Fresh Edge1 acceptance — Communications Relay and workspace

Phase 14J remains accepted:

- authoritative native Relay database `/var/lib/wwcx-comms/comms.sqlite3` retained as `0600 wwcx-comms:wwcx-comms`;
- snapshot service identity `wwcx-comms:wwadmin`;
- native database file read-only/query-only and article bodies excluded;
- required SQLite WAL/SHM sidecar access bounded to the containing directory;
- snapshot `/var/lib/wwcx-communications-workspace/events.jsonl` `0640 wwcx-comms:wwadmin`;
- 168 canonical Relay/NNTP events generated, validated, and live-attached;
- `content_is_untrusted=true` and `mutation_authorized=false` preserved;
- POST returned HTTP 405;
- workspace loopback-only at `127.0.0.1:8095`;
- 15-minute snapshot timer enabled;
- adjacent UC services active and live repository worktree unchanged.

Rollback:

`/tmp/edge1-uc-evidence-20260818T073658Z/rollback-relay-activation-20260818T103350Z.sh`

Communications Relay and workspace are `runtime_ready` for the bounded metadata/read-only scope.

## MMS scanner/private quarantine runtime

NOT COMPLETE:

- no trusted scanner attached;
- no private quarantine-storage runtime attached;
- quarantine release remains unauthorized.

Durable Messaging PostgreSQL storage does not satisfy the separate MMS quarantine storage/scanner requirement. The fail-closed metadata foundation remains live and deliberately degraded until those security components are attached.

## Voice/SIP state

Historical `telephony.read` acceptance remains valid. Fresh service checks confirmed Asterisk, Kamailio, telephony analytics, and telephony console active. Fresh native CDR/CEL inspection found zero rows, so no fabricated call records were introduced merely to manufacture acceptance evidence.

Whether the final global safe-scope flag requires an additional fresh functional Voice/SIP read/status acceptance remains unresolved.

## Resource warning

Post-Phase-18 memory remained approximately 1.5 GiB available while the configured 1 GiB swap allocation remained almost fully consumed. No recent OOM activity was observed and the bounded PostgreSQL activation did not materially reduce available memory. Broad unnecessary service restarts should still be avoided while swap pressure remains unresolved.

## Remaining fresh acceptance work

1. Approved private MMS quarantine storage and trusted scanner integration with fail-closed degradation testing.
2. `mail.correspondence.read` only after an authoritative native Mail Room correspondence source is explicitly selected and authorized.
3. Fresh functional Voice/SIP acceptance if required for the final global runtime flag.
4. Final readiness/handoff reconciliation after the remaining safe-scope items are complete or explicitly blocked.

Do not use production calls, messages, or email as acceptance tests. Production SMS/MMS, mail send, call origination, routing, quarantine release, credentials, DNS/firewall/certificate/authentication changes, porting, STIR/SHAKEN, financial or contractual actions remain separately controlled.
