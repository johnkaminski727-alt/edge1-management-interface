# Cookie Monster Alpha

Last updated: 2026-08-22

## Verified implementation direction

- Alpha lives in `edge1-management-interface` as an isolated subsystem.
- Source input is read only; generated evidence must be outside the source tree.
- M0/M1 use synthetic/staging data, not canonical archive data.
- Operator UI is part of the deliverable, not deferred technical debt.
- Project mascot is an intentional first-class UI asset.
- Big Bird remains control-plane/orchestration; its Cookie Monster handoff is a bounded job contract, not archive authority.
- Fengus is a bounded worker with no direct archive credentials or direct archive path in its work-item contract.
- Human review is append-only; web mutation stays disabled until an authenticated operator transport is deliberately wired.
- Runtime cockpit publication is a separate atomic copy from generated evidence into a private web root; generated state is never copied back into Git.

## Implemented surfaces

- `server/cookie_monster_alpha.py`
- `server/cookie_monster_contract.py`
- `server/cookie_monster_review.py`
- `server/cookie_monster_fengus_worker.py`
- `server/cookie_monster_acceptance.py`
- `deploy/cookie-monster-fengus-worker@.service`
- `deploy/cookie_monster_runtime_publish.py`
- `tests/test_cookie_monster_alpha.py`
- `tests/test_cookie_monster_control.py`
- `tests/test_cookie_monster_acceptance.py`
- `tests/test_cookie_monster_runtime_publish.py`
- `src/web/cookie-monster/index.html`
- `src/web/cookie-monster/demo-status.json`
- `src/web/cookie-monster/assets/mascot.webp`
- `docs/cookie-monster/alpha-foundation.md`
- `docs/cookie-monster/alpha-m3-m5.md`
- `docs/cookie-monster/alpha-m6-acceptance.md`
- `docs/cookie-monster/runtime-publication.md`

## Closed review findings

Fen independently verified PR #512 and closed the M0-M2 source hardening review. Append-only provenance/idempotency, symlink containment and processing budgets are verified.

## M3-M5 source direction

1. M3 review decisions are separate hash-chained append-only events; approved/rejected are terminal in Alpha.
2. Big Bird jobs use `wwcx.cookie-monster.job.v1` with a dataset slug and deterministic idempotency key. Arbitrary filesystem paths/URLs/commands/credentials are not part of the handoff.
3. M4 Fengus execution is allowlisted and data-only. A hardened systemd unit denies network, archive/generated-store visibility and unbounded resources when later activated.
4. M5 ingestion read audit remains authoritative for source access; review decisions add human action evidence.
5. The UI shows review, Big Bird job and Fengus surfaces. Review buttons generate the exact bounded CLI action until authenticated web mutation transport is connected.

## M6 synthetic acceptance

A repeatable source-level M6 harness exercises the complete Alpha safety path against a generated five-file non-production dataset. It verifies read-only source behavior, exact duplicate detection, provenance/hash-chain integrity, repeat-run idempotency, append-only audit, bounded human review, Big Bird's path-free job contract, and Fengus allowlist/archive-denial behavior. The operator UI exposes `acceptance.json` through an M6 acceptance screen without claiming a live run when evidence is absent.

Pre-publication local acceptance result: PASS (5 records / 4 unique assets / 1 duplicate group / 0 provenance gaps / 0 unauthorized source writes / 0 Fengus out-of-allowlist jobs).

## M7 runtime publication source package

The private cockpit runtime-publication package is implemented source-side. It requires a valid generated `status.json`, validates every present JSON snapshot before mutation, keeps repository/generated/web roots disjoint, backs up the complete managed destination set, atomically publishes the UI plus status/review/job/acceptance snapshots, removes stale optional runtime state, emits a SHA-256 publication manifest and supports exact managed-file rollback.

Local validation before publication: Python compile PASS and 6/6 targeted runtime-publication tests PASS.

This closes the source implementation gap for runtime packaging. It does not claim a live Edge1 apply: the currently exposed Edge1 Operator connector remains read-only.

## Remaining activation work

1. Select and create a non-production staging dataset mapping on Edge1.
2. Run the runtime publisher preflight and apply through an authenticated write-capable Edge1 path after generating a real non-production status snapshot.
3. Decide/wire the authenticated operator transport for actual web approve/reject clicks.
4. Create the Fengus runtime user/directories and activate the hardened worker service only after deployment review.
5. Re-run M6 against the deliberately selected Edge1 non-production staging dataset after runtime publication, with zero provenance gaps and zero unauthorized writes.
