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

## Implemented surfaces

- `server/cookie_monster_alpha.py`
- `server/cookie_monster_contract.py`
- `server/cookie_monster_review.py`
- `server/cookie_monster_fengus_worker.py`
- `server/cookie_monster_acceptance.py`
- `server/cookie_monster_runtime.py`
- `config/cookie_monster/datasets.json`
- `deploy/cookie-monster-fengus-worker@.service`
- `deploy/cookie-monster/publish.sh`
- `tests/test_cookie_monster_alpha.py`
- `tests/test_cookie_monster_control.py`
- `tests/test_cookie_monster_acceptance.py`
- `tests/test_cookie_monster_runtime_packaging.py`
- `src/web/cookie-monster/index.html`
- `src/web/cookie-monster/demo-status.json`
- `src/web/cookie-monster/assets/mascot.webp`
- `docs/cookie-monster/alpha-foundation.md`
- `docs/cookie-monster/alpha-m3-m5.md`
- `docs/cookie-monster/alpha-m6-acceptance.md`
- `docs/cookie-monster/runtime-packaging.md`

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

## Runtime packaging boundary

- The repository-controlled dataset registry now defines the intended `synthetic-media-v1` staging namespace but keeps it disabled by default.
- Runtime execution resolves only registered enabled dataset names, refuses canonical archive entries, and refuses paths outside `/srv/cookie-monster/staging/`.
- The Cookie Monster publisher is dry-run by default, backs up before apply, provides an exact rollback script, and publishes only the cockpit, mascot, and bounded derived JSON views.
- Raw knowledge, audit, and review-decision ledgers are intentionally not copied to the browser web root.
- Missing derived runtime evidence is removed on apply rather than leaving stale evidence visible.

## Remaining activation work

1. Verify/synchronize the intended Edge1 checkout before any Cookie Monster publication.
2. Deliberately create and enable the non-production staging dataset mapping on Edge1; the source registry remains disabled by default.
3. Run M6 against that Edge1 staging dataset and publish only bounded derived evidence to the cockpit.
4. Decide/wire the authenticated operator transport for actual web approve/reject clicks.
5. Create the Fengus runtime user/directories and activate the hardened worker service only after deployment review.
6. Promote Cookie Monster into the shared operator navigation only after the browser route and owning authorization boundary are verified live.
