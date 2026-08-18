# WW.CX Unified Communications — Relay Snapshot Live Acceptance

Date: 2026-08-18
Host: `edge1.ww.cx`
Repository source commit: `f5cf3047965a28a23ddc249c2c2f57ea167f7da8`
Operator evidence root: `/tmp/edge1-uc-evidence-20260818T073658Z`

## Accepted live state

Phase 14J completed successfully on Edge1 and attached the authoritative Communications Relay metadata snapshot to the persistent read-only Communications workspace.

Accepted runtime state:

- `edge1-comms-relay.service` active;
- `wwcx-communications-workspace.service` active;
- canonical snapshot generator installed as `wwcx-communications-relay-snapshot.service`;
- periodic refresh timer `wwcx-communications-relay-snapshot.timer` enabled and active;
- refresh cadence 15 minutes;
- generator identity `wwcx-comms:wwadmin`;
- generator reads the authoritative Relay SQLite database in read-only/query-only mode;
- authoritative database `/var/lib/wwcx-comms/comms.sqlite3` remained `0600 wwcx-comms:wwcx-comms`;
- SQLite WAL/SHM sidecars are permitted in `/var/lib/wwcx-comms` while the database file itself remains explicitly read-only inside the generator service namespace;
- persistent snapshot `/var/lib/wwcx-communications-workspace/events.jsonl` created as `0640 wwcx-comms:wwadmin`;
- snapshot contained 168 canonical `wwcx.communications-event.v1` events;
- workspace user `wwadmin` validated all 168 events before attachment;
- live workspace returned 168 events after attachment;
- every returned event retained authoritative native-record provenance to `edge1-comms-relay`;
- returned content remained `content_is_untrusted: true`;
- workspace remained `mutation_authorized: false`;
- POST to the events endpoint returned HTTP 405;
- listener remained loopback-only on `127.0.0.1:8095`;
- live `/opt/edge1-management-interface` worktree status was unchanged before and after activation;
- adjacent Messaging, Mail, BigBird, Asterisk, Kamailio, telephony analytics, telephony console, Relay, and Suricata services remained active;
- no SMS/MMS, email, calls, route changes, credential changes, or public listener changes occurred.

Rollback retained at:

`/tmp/edge1-uc-evidence-20260818T073658Z/rollback-relay-activation-20260818T103350Z.sh`

## Source classification

The accepted snapshot contains 168 Relay/NNTP metadata events sourced from the authoritative Relay database. Earlier Phase 13 validation established the live source distribution as 147 internal records and 21 inbound external-feed records. Article bodies are not selected or copied into the unified snapshot, and raw author identity is replaced by a SHA-256 identity reference.

## SQLite runtime findings

The Relay database uses WAL journal mode. Earlier failed activation attempts established two separate runtime requirements:

1. the snapshot generator must run as the database owner `wwcx-comms` because the authoritative database is intentionally mode `0600`;
2. a WAL reader may need to create/open SQLite `-wal` and `-shm` sidecars in the containing directory even when the database connection is read-only.

The merged service therefore runs as `wwcx-comms:wwadmin`, keeps `/var/lib/wwcx-comms/comms.sqlite3` explicitly read-only inside the service namespace, and permits bounded write access to `/var/lib/wwcx-comms` for SQLite sidecars plus `/var/lib/wwcx-communications-workspace` for the generated snapshot.

## Readiness interpretation

This acceptance changes the truthful runtime state for two surfaces:

- `communications_relay.edge1_runtime` => `runtime_ready`;
- `communications_relay.live_acceptance` => `runtime_ready`;
- `communications_workspace` remains `runtime_ready`, now with an attached authoritative canonical feed instead of an intentionally empty state.

It does **not** set global `fresh_edge1_runtime_verified` to true. Remaining safe-scope blockers still include:

- Messaging Gateway durable persistence (`storage` remains `memory`);
- trusted MMS scanner and private quarantine storage;
- authoritative native Mail Room correspondence/thread source for `mail.correspondence.read`;
- fresh functional Voice/SIP acceptance if required for the final global flag.

Production traffic authorization remains separately blocked. This acceptance does not authorize SMS/MMS send, mail send, call origination, route/trunk/dialplan mutation, quarantine release, provider activation, credentials, DNS/firewall changes, or other separately controlled actions.

## Resource note

Post-activation memory remained approximately 1.5 GiB available, but the configured 1 GiB swap allocation remained fully consumed. The successful Relay/workspace acceptance does not remove the separate host memory/swap pressure concern; avoid unnecessary broad service restarts until that resource issue is addressed independently.
