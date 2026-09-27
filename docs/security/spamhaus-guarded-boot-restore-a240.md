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

## Assignment 242 — Debian 13 live-JSON confirmation and rollback ownership gate

The operator's September 27 read-only diagnostics show Debian 13, kernel 6.12.107+deb13-amd64, systemd 257, synchronized Chrony, all four protective services active and a live table with 1,610 IPv4 / 85 IPv6 aggregated prefixes. Each of input and forward has exactly one `ip saddr == @drop4` and one `ip6 saddr == @drop6` match, followed in order by counter and DROP. The strict verifier has been tightened to match this observed JSON form; set elements and firewall backup contents were not published.

**Unresolved release blocker: ownership between rollback arming and candidate creation.** A scoped deletion that checks only the table name could delete an unrelated same-named table created by another process after the watchdog was armed. A pre-apply absence check is not sufficient: the check and the candidate-apply transaction are separate operations. Do not deploy, enable or execute the draft guard on a host whose table may be managed concurrently until the pending watchdog can reliably attest that this specific restoration attempt created the table.

Proposed solution for an *isolated* proof of concept: bind an unpredictable run identifier to the newly created table using an nftables table comment, embed the identifier atomically when creating the reviewed candidate, and have a separate rollback wrapper require the exact identifier before invoking the existing table-specific recovery program. The nftables man page supports table comments and distinguishes `create table` (error if already present) from `add table` (idempotent). An atomic candidate-plus-comment derivative must be proven equivalent to the pinned source except for the run identifier and strict create-only semantics. Confirm actual Debian 13 syntax using `nft --check` and an isolated non-production table namespace before coding deployment. A watchdog must never infer ownership merely from the presence of `inet bigbird_spamhaus`.

## Assignment 243 — Operator-confirmed syntax checks

The operator executed `nft --check --file` on two temporary, unrelated `inet edge1_a243_syntax_probe` inputs. The ordinary table comment and combined `create table` plus tagged table definition **both passed syntax checks**. The original `inet bigbird_spamhaus` table remained present and no syntax-probe table was created. This confirms the Debian 13 parser accepts the proposed form; it does **not** establish that executing the combined transaction succeeds atomically or that rollback deletion is race-free.

## Assignment 244 — Ownership candidate prototype (no deployment)

Added a pure, offline `spamhaus_ownership_candidate.py` source transformer plus regression tests. It takes an already validated canonical Spamhaus candidate and an unpredictable 128-bit run ID and produces a proposed `create table` statement plus a table declaration with `comment "edge1-spamhaus-run:<id>"`. The candidate transformer is **not invoked** by the guarded restoration service and no changes have been made to the installed independent recovery helper.

**Release block remains:** A matching table comment followed by a separate scoped `delete table` is still susceptible to a time-of-check/time-of-use race if an uncooperative process replaces the table. Require either a demonstrably atomic ownership-checked delete primitive or independently verified exclusive control over *all* writers to the dedicated table throughout create, acceptance and rollback. A cooperative file lock alone does not exclude other privileged writers. Do not wire the ownership prototype into the boot service or run the unattended watchdog against production until this proof and failure injection succeed. A mismatched/absent marker must stop deletion and preserve evidence; a matching marker is necessary but not sufficient if ownership can change before the deletion.

## Assignment 245 — Fail-closed read-only ownership classification

The repository now contains `spamhaus_ownership_inspect.py` and offline tests that classify an nftables table listing as `absent`, `owned`, `foreign` or `invalid` when presented with an expected 128-bit run ID. Malformed JSON, duplicate target-table records and forged run IDs are rejected. **This inspector never runs nftables and never authorizes deletion.** An `owned` finding is not race-free: without exclusive control over *all* privileged writers (or an atomic compare-and-delete primitive), a process can replace the table after the check. The watchdog and the original scoped recovery are therefore deliberately *not connected* to the prototype.

A244 initial repository-wide CI caught a truncated-candidate acceptance bug in the prototype, corrected by requiring balanced braces. The custom offline workflow was also corrected to use proper YAML line breaks and now exercises both ownership prototype modules. GitHub CI must pass on the final revision; prior success on earlier commits does not establish current acceptance.

## Assignment 246 — Isolated create-only execution rehearsal (prepared, not run)

The repository includes `tests/rehearse_spamhaus_ownership_netns.sh`, a single operator-run script for Edge1. It creates a **new network namespace**, verifies its namespace inode differs from the production host's before any nftables mutation, then attempts the syntactically approved create-only transaction **on a test table in that isolated namespace only**. It checks the resulting table comment, confirms a duplicate create is refused, deletes the isolated test table, then returns to a read-only verification that the production Spamhaus table exists. The temporary configuration is cleaned up by a shell exit trap. CI syntax-checks the script but cannot validate Edge1's real kernel namespace permissions or nft runtime behavior.

This is an optional later operator step after review. If `sudo unshare --net` is unavailable, abort the rehearsal without fallback to the production namespace. **Do not substitute `sudo nft -f` directly on the host.** This rehearsal does not exercise systemd timers or resolve the ownership-check/delete race, so PR #607 remains draft afterward regardless of the syntax test's result.

## Assignment 246 live rehearsal — FAILED SAFELY; original script retired

The operator fetched the pinned draft revision `ddcdf57ee1e42b9c3d741b7c690b8417103a51bc` and ran the separate-netns rehearsal on Debian 13. New namespace isolation was **confirmed**. The test nft transaction did not error, but the JSON table-comment assertion failed; consequently the script exited early without completing the duplicate-create test, isolated-table deletion step or final read-only host verification. No production nft command was issued by that isolated step. The operator's SSH connection also closed; shell `set -e` can explain that on an uncaught nonzero exit, but service availability must be separately reconfirmed. Do not represent production connectivity or table health as verified after the failed command.

Root-cause candidate: the A244 prototype attached the comment to a *second* `table inet ... { comment ... }` block after an initial **bare** `create table`. Parsing that block successfully does not prove it mutates the metadata of an already-created table. Debian nft's documented table grammar permits attaching the comment to the `create table ... { comment ... }` command itself. Updated the pure derivation tests and the isolated rehearsal to do so; this is **not a confirmed fix** until independently exercised on Edge1. The prior pinned rehearsal must not be rerun. Never fall back to applying the nft transaction in the production network namespace.

The core race-free deletion/ownership release blocker remains unchanged even if the revised create syntax works. Do not merge, deploy or enable the proposed guarded service before an atomic-owner conditional deletion primitive or proven exclusive control over privileged writers exists.

## Assignment 246B — Corrected comment requires statement terminator

On Edge1, the corrected draft revision `c49ecd635e9fc8ccd37e71e34763b76d5acadf8e` was fetched and the isolated namespace check again passed. The test stopped during `nft --check` before applying any nftables transaction: the parser reported `unexpected '}', expecting newline or semicolon` after the `comment` directive. No duplicate-create or ownership readback testing occurred. The SSH shell remained open. The earlier independent host health check showed all critical services active, the live Spamhaus table present, and automatic restoration still not installed.

The A246B incident reveals that the attempted inline `create table ... { comment "..." }` form requires a statement terminator **between** the comment and closing brace. The repository generator, offline expected-output test and isolated rehearsal now use `create table ... { comment "..."; }`. This is a syntactic correction inferred directly from the live parser error. **Not yet runtime-validated**: require a syntax-only `nft --check` pass on Edge1 before retrying the isolated execution rehearsal. Do not modify production firewall tables or attempt the original failed commits. A passing rehearsal still does not solve the independent ownership check/delete race.

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
