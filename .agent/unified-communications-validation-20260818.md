# Unified Communications — Validation Record

Date: 2026-08-18
Scope: repository-side completion, CI evidence, and fresh authenticated Edge1 operator acceptance
Global fresh runtime completion: partial; Relay canonical feed, persistent workspace, durable Messaging PostgreSQL state, and bounded Voice/SIP read-only acceptance are complete, while MMS scanner/storage and Mail correspondence remain incomplete

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
| #409 | Durable Messaging PostgreSQL acceptance reconciliation | merge `7ca3b8360de740d844edcb8c598b1988407a16e5` | PASS |

## Evidence interpretation

Repository CI and operator-run Edge1 evidence are distinct. Green GitHub Actions workflows establish repository validation only. Fresh live claims below come from authenticated operator-run SSH acceptance on `edge1.ww.cx`.

The global `fresh_edge1_runtime_verified` flag remains false until the intended safe-scope runtime surfaces are complete or explicitly resolved. Fresh runtime acceptance does not imply production-traffic authorization. A functional read-only acceptance may coexist with a degraded operational-health result; those states are recorded separately rather than collapsed into a single claim.

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
- local `PostgresEventStore` smoke test passed ping, zero count, and initialized control state;
- a second zero-event state-loss gate passed immediately before restart;
- `DATABASE_URL` configured as a Unix-socket DSN with no database password;
- only `wwcx-messaging-gateway.service` restarted for the storage switch;
- post-restart `/readyz` returned `storage: postgres`;
- live HTTP event count and PostgreSQL event count both returned zero;
- PostgreSQL enabled for reboot persistence only after functional validation;
- adjacent UC services remained active;
- post-activation `MemAvailable` remained approximately 1.5 GiB and no new OOM evidence was observed;
- no SMS/MMS, provider routing, public database listener, database password, or credentials were generated or changed.

Rollback:

`/tmp/edge1-uc-evidence-20260818T073658Z/rollback-messaging-postgres-20260818T111017Z.sh`

Messaging durability is freshly `runtime_ready` and no longer a blocker.

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

## Fresh Edge1 acceptance — Voice/SIP, Phase 19

PASS for the bounded read-only functional surface:

- repository-provided telephony analytics acceptance audit ran on `edge1.ww.cx` with evidence directory `/var/lib/wwcx-deployment-evidence/telephony-analytics-live-acceptance/uc-phase19-20260818T112551Z`;
- Asterisk, Kamailio, telephony analytics, and telephony console services were active before and after the audit;
- audited telephony assets matched current `origin/main` baseline `7ca3b8360de740d844edcb8c598b1988407a16e5`;
- runtime analytics API and telephony-platform source hashes matched canonical repository sources;
- analytics service remained hardened and loopback-only on `127.0.0.1:8099`;
- health, calls-summary, and interconnect-summary aggregate endpoints returned valid payloads;
- payload validation, privacy scanning, and anomaly-contract validation passed;
- POST to the read-only platform-health endpoint returned HTTP `405`;
- audit decision reported `warnings=0`, `failures=0`, `listener_scope=loopback-only`, and `api_mode=read-only`;
- audit explicitly reported `database_query_performed=no`, `credentials_read=no`, `customer_identifiers_retained=no`, `call_origination_performed=no`, `dtmf_transmission_performed=no`, `carrier_route_changed=no`, `service_mutation=none`, and `runtime_mutation=none`;
- Asterisk reported zero active calls and zero calls processed at acceptance time;
- adjacent Messaging PostgreSQL, Communications workspace, Relay, and BigBird services remained active;
- available memory remained approximately 1.5 GiB after the audit.

The bounded read-only Voice/SIP `live_acceptance` is therefore `runtime_ready`.

Operational health remains DEGRADED and is not overwritten by the passing acceptance:

- aggregate `overall_status` was `critical` with score `28`;
- component `sip` was `degraded`;
- one of two interconnects was failed and `attention_required=1`;
- interconnect attention ratio was in critical state;
- no call sample existed, so answer/failure-rate anomaly indicators correctly reported insufficient data.

The readiness matrix therefore records `voice_sip.edge1_runtime = degraded` while `voice_sip.live_acceptance = runtime_ready`. No call origination, route/trunk/dialplan/emergency changes, or provider traffic authority is inferred.

## MMS scanner/private quarantine runtime

NOT COMPLETE:

- no trusted scanner attached;
- no private quarantine-storage runtime attached;
- quarantine release remains unauthorized.

Durable Messaging PostgreSQL storage does not satisfy the separate MMS quarantine storage/scanner requirement. The fail-closed metadata foundation remains live and deliberately degraded until those security components are attached.

## Resource warning

Post-Phase-19 memory remained approximately 1.5 GiB available while the configured 1 GiB swap allocation remained almost fully consumed. The Phase 19 audit did not restart services or create new communications traffic. Broad unnecessary service restarts should still be avoided while swap pressure remains unresolved.

## Remaining fresh acceptance work

1. Approved private MMS quarantine storage and trusted scanner integration with fail-closed degradation testing.
2. `mail.correspondence.read` only after an authoritative native Mail Room correspondence source is explicitly selected and authorized.
3. Investigate Voice/SIP operational degradation without confusing that follow-up with the already-passed bounded read-only acceptance.
4. Final readiness/handoff reconciliation after the remaining safe-scope blockers are complete or explicitly resolved.

Do not use production calls, messages, or email as acceptance tests. Production SMS/MMS, mail send, call origination, routing, quarantine release, credentials, DNS/firewall/certificate/authentication changes, porting, STIR/SHAKEN, financial or contractual actions remain separately controlled.
