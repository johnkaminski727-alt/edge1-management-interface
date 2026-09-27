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

## Assignment 246C — Operator syntax confirmation and exact-form follow-up

The operator executed `nft --check --file` on Edge1 using a **multiline** create-only test-table definition with a semicolon-terminated ownership comment, followed by the interval set and input rule. The parser returned success and a separate read-only check confirmed the production Spamhaus table still exists. This was a **syntax check only**, not a transaction execution or ownership-readback check.

The staged tagged-candidate generator, exact-output offline test, and isolated network-namespace rehearsal were updated to use the same operator-tested multiline statement. Before an operator runs the revised isolated execution script, pin the GitHub commit and verify its complete CI status. Neither this syntax gate nor a successful isolated create-only rehearsal resolves the separate non-atomic check/delete race. The production restore service remains disabled and the PR remains draft.

## Assignment 246D — Isolated ownership execution rehearsal PASSED

The operator fetched pinned commit `64f1dbd8c9fa805cdc185dfe1c824ae3ec63f93d` and executed `tests/rehearse_spamhaus_ownership_netns.sh` on Edge1's Debian 13 kernel. The actual operator transcript reports: network namespace isolation confirmed; create-only transaction and table comment verified; duplicate create refused; isolated test table deleted; production Spamhaus table present. An additional independent host read-only nft check confirmed the production table present; rehearsal exit status 0, interactive shell retained.

This confirms the revised **multiline** create-only tagged statement functions in a separate nftables network namespace with Edge1's runtime. It does **not** establish race-free check/delete, test systemd transient timer behavior, demonstrate external acceptance, or authorize installing/enabling the current guarded service. Treat the ownership readback as a necessary integrity check, **not deletion authorization**. The separate time-of-check/time-of-use release blocker remains open and draft PR #607 must remain unmerged.

## Assignment 247 — Per-attempt isolated table prototype (STAGING ONLY)

The separate-network-namespace execution rehearsal passed at pinned commit `64f1dbd8c9fa805cdc185dfe1c824ae3ec63f93d`, verifying that a tagged create-only table can be created, inspected and cleaned up without affecting the host's live Spamhaus table. This establishes syntax and basic nft runtime semantics, **not** atomic conditional rollback.

To reduce the accidental cross-attempt deletion risk, Assignment 247 prototypes a **different table name for each restoration attempt**, `inet bigbird_spamhaus_run_<128-bit-random-hex>`, with an identically bound ownership comment. A watchdog for one attempt would refer only to that attempt's unique table name. A subsequent attempt gets a different name and must never be removed by the earlier watchdog. The canonical `inet bigbird_spamhaus` table and protected pinned candidate remain unchanged. The pure `spamhaus_run_scoped_candidate.py` transformer and offline tests implement the proposed naming, expected comment and fail-closed *read-only* ownership classification. These prototypes do not install any watchdog, execute nftables, alter the original scoped recovery, or invoke the current guarded boot orchestrator.

**Threat-model distinction:** unpredictable unique names address *accidental deletion across independent cooperating restoration attempts*, not malicious or arbitrary out-of-band root writers. A privileged process that learns the run name may still replace it between a read-only ownership check and a name-based deletion. A marker match is never proof of an atomic compare-and-delete operation. Require independent authorization/coordination over all writers, a genuine atomic ownership-check/delete design, or explicitly narrow and approve the threat model before integrating any automatic rollback. Multiple per-run tables also require a reviewed lifecycle, guaranteed stale-table cleanup, and proof that simultaneously attached input/forward hooks do not change intended filtering; run-scoped tables cannot simply be enabled in production as a drop-in replacement.

**Additional deployment gates:** rehearse actual per-run nft creation and mismatch/duplicate injection in an isolated namespace, test systemd transient timer properties, choose the correct timeout, prove external SSH reachability and authenticated unattended acceptance, and secure independently installed root-only recovery. A missing table on boot does not license unguarded application. The current draft helper still targets the legacy dedicated table and must **not** be installed or run with `--execute` until redesigned.

The dedicated custom CI workflow had escaped literal `\\n` between steps, which prevented its proper parsing; Assignment 247 replaces those with actual YAML newlines and adds per-run regression coverage. Confirm the workflow **actually runs and passes** on the final commit instead of relying only on repository-wide CI.

## Assignment 247 — Dual-run isolated execution rehearsal prepared

A separate, operator-optional `tests/rehearse_spamhaus_run_scoped_netns.sh` has been staged and shell-syntax checked in CI. It uses fixed **test-only** distinct run IDs and temporary root-private input files; requires a newly created network namespace to have a different inode **before** any nft mutation; loads two differently named tagged tables only within that namespace; proves the two coexist, duplicate creation is rejected, and deleting test run A leaves B's table and ownership marker unchanged; finally deletes B and independently checks the original production Spamhaus table read-only. Failure of `unshare --net` must abort, without falling back to the production namespace.

This is **not an autonomous rollback rehearsal**, and cannot demonstrate safety against an uncooperative privileged writer who knows another run's table name. Neither the current guarded service nor the independently installed legacy recovery are modified or enabled. A production rollout would need explicit design approval for the new per-run table lifecycle and separate positive-acceptance, controlled stale-table cleanup, sandbox and timer tests.

## Assignment 247 — Edge1 dual-run rehearsal PASSED

The operator fetched pinned commit `ffd0294ee8518f71fdaa197e145baf1f77ad5569` and ran `tests/rehearse_spamhaus_run_scoped_netns.sh` on Edge1. The provided terminal output confirms all tests passed: a distinct network namespace was verified, two differently named owner-tagged tables coexisted, duplicate creation was refused, deleting run A did not delete or alter run B, both isolated run tables were cleaned up, and both the script's original-namespace check and an independent host check confirmed the production `inet bigbird_spamhaus` table was still present. The wrapper returned status 0 and the operator retained the SSH session.

This **completes isolated dual-run table lifecycle verification only**. It does not establish safe unattended restoration, a real watchdog rollback, protection against uncooperative privileged writers or independent external acceptance. The original dedicated-table recovery still deletes `inet bigbird_spamhaus` by name; it is intentionally not connected to the per-run prototype. Keep draft PR #607 unmerged, the guarded restore service uninstalled and automatic feed updates disabled.

### Assignment 248 release gates

1. Design a per-run watchdog that never targets the canonical production table, rejects foreign/missing ownership and records immutable run identity and rollback evidence. A matching comment alone is not atomic check/delete: require verified exclusive coordination across all privileged writers or a genuinely atomic conditional deletion primitive before automatic deletion.
2. Independently validate Debian 13/systemd 257 transient timer target and `ExecStart` behavior using a harmless, non-firewall rehearsal. Confirm timer arming before any firewall mutation, timer fire/failure evidence, and behavior if the initiating process dies.
3. Specify positive acceptance using an independently authenticated external reachability receipt, bound to boot ID/run ID/candidate hash/expiry, with explicit watchdog disarming only upon verified acceptance. Without acceptance, rollback must remain scheduled.
4. Reconcile unique-table hook behavior, conflicts and stale-table cleanup with the existing canonical `bigbird_spamhaus` table. Test duplicate and interrupted operations in an isolated network namespace, and rehearse scoped recovery failure without touching production.

## Assignment 248 — Harmless independent systemd timer rehearsal PREPARED

Added `tests/rehearse_spamhaus_systemd_timer_noop.sh`, a **not-yet-executed** operator-optional script that creates a uniquely named transient 15-second timer running only `/usr/bin/true`. It checks `ActiveState`, `Unit` target, and the complete harmless service executable before observing whether the independently scheduled no-op service fires. A shell exit trap stops/resets only these uniquely named ephemeral probe units. CI checks shell syntax. This is an isolated **systemd control-plane diagnostic**, not a safe rollback implementation or an external acceptance test.

**Safety restrictions:** The test contains no nftables calls, no reboot, no persistent unit installation and no production service enablement. Do not run the original draft guarded `--execute` flow as a substitute. An actual watchdog for uniquely named per-run firewall tables still requires scoped ownership checks and deletion race analysis, root-only installed helpers, independent health verification, forensic evidence, failure injection and authenticated external positive acceptance. This script must be reviewed before any operator-run execution, and its future PASS would demonstrate only systemd transient scheduling.

## Assignment 248 — timer rehearsal cleanup guard review

Before the harmless transient timer test was handed to the operator, its shell exit trap was restricted to stop/reset the uniquely named probe units **only after the `systemd-run` command successfully returned**. If the initial name-collision check fails or the timer fails to arm, cleanup does not stop an existing unit. The probe's service command remains only `/usr/bin/true`, with no nftables operations, no persistent unit installation and no reboot. This is a no-op test of systemd scheduling, not evidence that the unfinished legacy restore helper is safe for unattended execution.

## Assignment 248 — Edge1 independent no-op timer PASSED

The operator fetched pinned revision `edd7fc74338c21b0df6fba2e9bf221ec466825e8` and ran `tests/rehearse_spamhaus_systemd_timer_noop.sh` on the production Edge1 **without making firewall changes**. The actual transcript shows systemd created a uniquely named transient `edge1-spamhaus-a248-probe-65474.timer` targeting the matching `.service`; the timer's ActiveState was `active`, and systemd's ExecStart was precisely `/usr/bin/true`. The service's nonzero start timestamp and Result=`success` demonstrated independent execution; the test reported PASS and cleaned up its own transient probe units. Both the script's independent host firewall check and exit status 0 were recorded, and the operator's interactive SSH session remained open.

**Evidence gap:** The unprivileged `journalctl -u ...` printed `-- No entries --` with a notice that the user cannot see all journal entries. This is not proof that systemd failed to record the event. A later **sudo read-only journal query** or a separate harmless failure-injection rehearsal must verify actual journal visibility and incident logging; do not misstate this as a demonstrated journal record. An independent systemd no-op timer firing does not establish persistent boot restore correctness, sandbox compatibility, rollback ownership or recovery failure behavior. The canonical production table, boot service, and feed-update settings are untouched.

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
