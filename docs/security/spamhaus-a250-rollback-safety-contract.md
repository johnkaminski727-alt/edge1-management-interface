# Assignment 250 — Unattended rollback safety contract (DESIGN ONLY)

Status: offline design proposal; no production installation, automatic restore, timer enabling, firewall mutation or reboot is approved. This document is a release-gating contract, not executable recovery software.

## Validated foundation

- A246D confirmed that Debian 13 nftables creates a table with an ownership comment when a semicolon-terminated comment is included in a create-only transaction; duplicate create is rejected in a new network namespace.
- A247 confirmed two independently named and tagged per-run tables can coexist in a new network namespace; deletion of isolated run A left B unchanged. This does not prove concurrency safety against uncooperative root-level writers.
- A248/249 confirmed harmless transient systemd services run independently, success and failure are observable, and root can read the actual failure journal.
- The existing installed `spamhaus_scoped_recovery.py --execute` deletes the shared `inet bigbird_spamhaus` table by name. It is NOT a safe per-run watchdog. The current draft guarded boot helper must not be installed or invoked with `--execute`.

## Security boundary and release decision

**The existence of a table and matching comment is not deletion authorization.** A separate nft JSON ownership read followed by a name-only delete cannot exclude another privileged writer replacing the table between commands. Randomized table names and cooperative locks reduce accidental cross-run errors, but do not eliminate this race for unrestricted root writers.

The system must not automatically delete a firewall table until one of these alternatives has been verified and approved:

1. Demonstrate an actual atomic, kernel-enforced identity/ownership conditional deletion operation on the deployed nftables version, with failure injection proving it cannot delete a replacement table; **or**
2. Establish a realistically enforceable *exclusive-writer threat model*, including actual confinement/ownership over every privileged actor permitted to mutate the managed per-run tables for the entire timer, acceptance and rollback lifecycle. A simple advisory lock is insufficient. Explicitly list all remaining privileged bypasses and prohibit automatic deletion if exclusivity cannot be established.

If neither alternative can be satisfied, retain the watchdog as **detect-and-alert only**, preserve the table and require a trusted operator to investigate/recover. Do not reclassify this as successful automatic rollback.

## Required state machine and invariants

Proposed phases: `prepared`, `watchdog_armed`, `created_unaccepted`, `externally_accepted`, `rollback_requested`, `rollback_verified`, `foreign_or_ambiguous`, `incident`. Every transition must be accompanied by durable evidence, linked to boot ID, random run ID, table name, pinned candidate SHA-256, and timer unit.

1. `prepared -> watchdog_armed`: validate installed root-owned helpers and protected candidate; arm and verify independent timer before *any* nft mutation. A timer that does not target the exact expected immutable recovery executable fails closed.
2. `watchdog_armed -> created_unaccepted`: only a create-only nft transaction for the *unique* per-run name, with its owner marker, may proceed. Duplicate create or any unexpected existing table is a stop, not permission to replace.
3. `created_unaccepted -> externally_accepted`: a trusted external verifier checks actual reachability and signs/authenticates a fresh acceptance receipt bound to boot ID, run ID, exact candidate hash and expiry. Local service-active results do not authorize timer cancellation. Authenticate and persist receipt *before* disarming.
4. `created_unaccepted -> rollback_requested`: timer fires on the expected run only. If there is no proven atomic deletion or exclusive-writer guarantee, record `foreign_or_ambiguous` and alert rather than run name-only `nft delete table`.
5. `rollback_requested -> rollback_verified`: only after a permitted deletion operation can prove the exact run-owned object was removed without touching other tables. Capture before/after evidence and systemd journal. A failed operation transitions to `incident` without broadening its deletion scope.
6. Repeated invocation, old timer firing, absent/mismatched table, altered run metadata, timeout, reboot mid-operation, or later run creation must NEVER cause deletion of `inet bigbird_spamhaus` or another run's table.

## Offline regression matrix before another live test

| Scenario | Required outcome |
|---|---|
| Matching run/table and valid protected metadata, but no proven exclusive writer | Detect and alert; **no delete** |
| Absent table | Idempotent absence record; no delete |
| Same name, wrong/missing comment | Foreign-table incident; no delete |
| Malformed nft JSON, duplicate matching records, missing run identity | Fail closed; no delete |
| Newer run B created after older run A | A's watchdog cannot address B's name |
| Another privileged writer replaces A after a separate read | No automatic delete without verified atomicity/exclusivity |
| systemd timer/service mismatch or failure to arm | No nft mutation |
| No external positive acceptance by deadline | Timer remains armed; apply only proven-safe rollback or alert |
| Stale acceptance, wrong boot/run/hash, replayed receipt | Refuse disarm; audit |
| Actual deletion fails | Incident, retained forensic evidence; no global ruleset restore |

## Deployment separation

All initial tests are pure functions/mocks and separate network namespaces. A harmless systemd timer rehearsal is already complete, but no production reboot, auto-feed refresh, production namespace nft modification, watchdog installation, or merge is authorized. Draft PR #607 remains blocked pending verified deletion semantics or explicitly approved exclusive-writer policy, durable incident evidence, and independent acceptance.
