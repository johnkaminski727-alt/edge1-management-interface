# Unified Communications — Validation Record

Date: 2026-08-18
Scope: repository-side completion, CI evidence, and fresh authenticated Edge1 operator acceptance
Global fresh runtime completion: partial; Relay canonical feed and persistent workspace are accepted, while Messaging durability, MMS scanner/storage, Mail correspondence, and any required fresh Voice/SIP acceptance remain incomplete

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
| #407 | SQLite WAL/SHM sidecar sandbox correction | merge `f5cf3047965a28a23ddc249c2c2f57ea167f7da8` | Unified Communications Validation PASS; Edge1 Operator Validation PASS; Validate repository PASS |

## Contract validations

Repository validation covers or is backed by focused tests for:

- canonical event validation and authoritative native-record provenance;
- rejection of embedded raw message/private/credential fields from the canonical layer;
- deterministic conversation ordering;
- metadata-only search allowlist;
- explicit-evidence identity links and rejection of name-similarity inference;
- retrieved/untrusted metadata inability to grant scopes or tool authority;
- quarantine release fail-closed behavior;
- SMS/MMS read-token enforcement and sanitized media projection;
- SMS/MMS draft != send;
- Mail draft != send and no network activity;
- provider/source failure-safe boundaries;
- loopback-only workspace binding and rejection of mutation verbs;
- hardened persistent workspace service deployment and rollback;
- metadata-only Relay canonical snapshot generation;
- Relay database read-only/query-only access;
- author identity hashing and article-body exclusion;
- fail-closed Relay source classification;
- corrected snapshot generator identity `wwcx-comms:wwadmin`;
- explicit read-only native database file plus bounded WAL/SHM sidecar directory access;
- JavaScript syntax and responsive workspace assets;
- MMS pending-scan, missing-digest, malicious, scan-error, and clean-held states.

## Evidence interpretation

`Edge1 Operator Validation` is a repository CI workflow name. Green CI remains CI evidence only. Fresh live claims below come from operator-run SSH acceptance against `edge1.ww.cx` and are kept separate from repository evidence.

The global `fresh_edge1_runtime_verified` flag remains false until the intended safe-scope runtime surfaces are complete. Fresh acceptance does not imply production-traffic authorization.

## Fresh Edge1 acceptance — Messaging Gateway

PASS:

- `wwcx-messaging-gateway.service` live as version `0.4.2`;
- health/readiness on loopback `127.0.0.1:58080`;
- authenticated `messages.status.read` and `messages.conversation.read`;
- recent conversation contract `wwcx.messages-conversation-read.v1`;
- untrusted-content marker and `mutation_authorized: false`;
- fail-closed MMS quarantine projection with `release_authorized: false`;
- no SMS/MMS traffic generated.

Known limitation: storage remains `memory`.

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

## Fresh Edge1 acceptance — Persistent Communications workspace

Phase 10 established the persistent service baseline:

- `wwcx-communications-workspace.service` installed, enabled, active, and running;
- identity `wwadmin:wwadmin`;
- listener `127.0.0.1:8095` only;
- health/readiness/static workspace HTTP 200;
- POST rejected with HTTP 405;
- live repository worktree unchanged;
- rollback retained.

That Phase 10 acceptance truthfully had zero events because no canonical feed was attached at that time. Phase 14J supersedes that empty-input state.

## Fresh Edge1 acceptance — Communications Relay canonical snapshot, Phase 14J

PASS:

- exact merged implementation source gate `f5cf3047965a28a23ddc249c2c2f57ea167f7da8`;
- authoritative native Relay database retained at `/var/lib/wwcx-comms/comms.sqlite3` as `0600 wwcx-comms:wwcx-comms`;
- snapshot service effective identity `wwcx-comms:wwadmin`;
- native database file explicitly read-only in the service namespace;
- containing Relay directory writable only for required SQLite WAL/SHM sidecars;
- snapshot output directory writable for the generated canonical JSONL;
- snapshot service completed with `Result=success` and exit status 0;
- generated snapshot `/var/lib/wwcx-communications-workspace/events.jsonl` owned `wwcx-comms:wwadmin`, mode `0640`;
- snapshot contained 168 events;
- workspace user validated all 168 events before attachment;
- every event retained `channel=nntp`, `native_record.source=edge1-comms-relay`, authoritative native provenance, and `quarantine_release_authorized=false`;
- workspace restart after attachment passed;
- live workspace returned 168 events;
- live response preserved `content_is_untrusted=true` and `mutation_authorized=false`;
- POST remained HTTP 405;
- periodic `wwcx-communications-relay-snapshot.timer` enabled with 15-minute cadence;
- workspace listener remained loopback-only on `127.0.0.1:8095`;
- all adjacent UC services and Suricata remained active;
- live repository worktree status compared identical before/after activation;
- no SMS/MMS, email, calls, route changes, credential changes, or public listener changes occurred.

Rollback:

`/tmp/edge1-uc-evidence-20260818T073658Z/rollback-relay-activation-20260818T103350Z.sh`

The Communications Relay and Communications workspace are now both freshly `runtime_ready` for this bounded metadata/read-only scope.

## MMS scanner/private quarantine runtime

NOT COMPLETE:

- no trusted scanner attached;
- no private quarantine-storage runtime attached;
- no package installation performed;
- quarantine release remains unauthorized.

The fail-closed metadata foundation is live, but security remains deliberately degraded until trusted scanning and private storage are attached.

## Voice/SIP state

Historical `telephony.read` acceptance remains valid. Fresh service checks confirmed Asterisk, Kamailio, telephony analytics, and telephony console active. Fresh native CDR/CEL inspection found zero rows, so no fabricated call records were introduced merely to manufacture acceptance evidence.

Whether the final global safe-scope flag requires an additional fresh functional Voice/SIP read/status acceptance remains unresolved.

## Resource warning

Post-Phase-14J memory remained about 1.5 GiB available, but the configured 1 GiB swap allocation remained fully consumed. This does not invalidate the accepted Relay/workspace functionality, but broad unnecessary service restarts should be avoided until host memory/swap pressure is investigated separately.

## Remaining fresh acceptance work

1. Durable private Messaging Gateway state instead of volatile `storage: memory`.
2. Approved private MMS quarantine storage and trusted scanner integration with fail-closed degradation testing.
3. `mail.correspondence.read` only after an authoritative native Mail Room correspondence source is explicitly selected and authorized.
4. Fresh functional Voice/SIP acceptance if required for the final global runtime flag.
5. Final readiness/handoff reconciliation after the remaining safe-scope items are complete or explicitly blocked.

Do not use production calls, messages, or email as acceptance tests. Production SMS/MMS, mail send, call origination, routing, quarantine release, credentials, DNS/firewall/certificate/authentication changes, porting, STIR/SHAKEN, financial or contractual actions remain separately controlled.
