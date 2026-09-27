# Assignment 240 — Guarded Spamhaus boot restoration (STAGING ONLY)

Date: 2026-09-27. Starting point: merged PR #606, commit `723e712775da5534042a146a725fa63a9da39421`.

## Scope and production exclusion

This branch is **not deployment approval**. The production `inet bigbird_spamhaus` table stays untouched; no executable, timer or service is installed or enabled. Auto feed updates stay disabled. Do not load a global nftables backup: iptables-nft owns unrelated tables. Run repository tests offline first; test independently installed, root-owned runtime copies in the later approved staging phase.

## Guarded algorithm

1. If `inet bigbird_spamhaus` already exists, return `already_present`. Do not arm a timer, replace the table or infer that an existing table was created by this boot attempt.
2. If absent, require chrony synchronization, active SSH/UFW/CrowdSec/bouncer services, protected source files and the existing pinned-candidate preflight. Preflight hashes the candidate and feed inputs, requires the installed recovery program to match the staged copy, rerenders the candidate and enforces each feed's 72-hour ceiling and 15-minute future-skew limit. Perform `nft --check --file` with the exact pinned candidate.
3. In explicit `--execute` mode only, start an independent transient `edge1-spamhaus-rollback.timer` using `systemd-run --on-active=180s`. Its service invokes only the independent `/usr/local/libexec/edge1-spamhaus/spamhaus_scoped_recovery.py --execute`. Confirm timer active, service target and complete command before any firewall mutation. If timer creation or verification fails, abort without applying.
4. Repeat preflight **after** arming and check table absence again. If it appeared in the meantime, refuse replacement and leave rollback armed for operator review. Never refresh feeds here.
5. Apply exactly `/var/lib/edge1-spamhaus/boot-candidate/spamhaus-candidate.nft`. Verify both nonempty interval sets, the input and forward filter hooks at priority -110, and one IPv4 plus one IPv6 source-set counter/drop rule per hook. Check critical services are still active.
6. Success is `restored_verified_rollback_armed`, **not operational acceptance**. All failures after arming leave the watchdog intact. Capture output in systemd's journal; preserve the systemd transient unit and journal evidence. Timer execution runs scoped deletion only.

## Unattended positive acceptance: deliberately unresolved deployment gate

The staged helper does **not** disarm the watchdog. Without a trusted independent acceptance channel it will revert the dedicated table after its 180-second deadline, including after locally successful restore. Local SSH-active status does not prove external SSH connectivity; the same machine should not self-approve it. A future separate approval-gated component may supply an authenticated external reachability receipt bound to the specific boot ID, candidate SHA-256, run ID and fresh deadline and then explicitly cancel the pending timer. That component must not be added to production until it is independently tested, resistant to replay and failure, and approved.

A reboot with a candidate older than 72 hours leaves the dedicated table absent, not restored from an expired snapshot. Refreshing involves a **separate** authorized, check-only feed acquisition, candidate rendering, exact checksum manifest, fresh validation, signed/reviewed source commit or approved provenance, protected staged rotation with atomic rename, and independent preflight. Automatic feed updates remain disabled throughout this assignment.

## Known limitations requiring independent rehearsal before installation

- Confirm actual Debian 13 `nft -j list table inet bigbird_spamhaus` JSON matches the strict verifier; schema handling is intentionally fail-closed.
- Confirm Debian 13 `systemd-run` transient timer naming, `systemctl show` values, root-only recovery installation and sandbox permissions in an isolated environment. `ProtectSystem=strict` is inherited from the proposed service and must be checked against the system manager IPC access required by systemd-run.
- The 180-second timer is for isolated rehearsal, not a final production safety interval. Choose a tested timer longer than the full boot preflight but shorter than unacceptable exposure, then validate failure injection, transient unit cleanup and repeated boot behavior.
- The separate scoped recovery's offline tests establish its nominal table-only operation; force recovery failure and verify persistent incident evidence and hosting-console escalation. Inability to remove the table is **not** silent success.
- Verify true external SSH access through an independent session and hosting-console/rescue recovery. Rollback must never restore a full historical ruleset.
- An unexpected duplicate table during the arm/apply race is a deployment stop. Do not use this staged helper against a live existing table for mutation tests.

## Assignment 240 test and review gates

`python3 -m unittest -v tests/validate_spamhaus_guarded_boot_restore.py` (or execute as a script), `python3 tests/validate_spamhaus_boot_restore_unit.py`, `python3 tests/validate_spamhaus_scoped_recovery.py`, and repository-wide CI must pass. CI mocks systemd/nftables; it is **not** an Edge1 boot or firewall test. The pull request must remain a draft while the timer verification and independent failure rehearsal are outstanding.

## Change record

- Added guarded, check-only-default orchestrator with pre-arm/source/service gates.
- Changed proposed non-enableable restore service to call the orchestrator instead of the unguarded executable.
- Added isolated tests for check-only, already present, stale feed, timer arm/state failures, apply failure, rule verification failure, watchdog retained on success/failure and scoped recovery fault.
- No production changes, no source/feed publication and no approved reboot.
