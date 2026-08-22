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
- `deploy/cookie-monster-fengus-worker@.service`
- `tests/test_cookie_monster_alpha.py`
- `tests/test_cookie_monster_control.py`
- `src/web/cookie-monster/index.html`
- `src/web/cookie-monster/demo-status.json`
- `src/web/cookie-monster/assets/mascot.webp`
- `docs/cookie-monster/alpha-foundation.md`
- `docs/cookie-monster/alpha-m3-m5.md`

## Closed review findings

Fen independently verified PR #512 and closed the M0-M2 source hardening review. Append-only provenance/idempotency, symlink containment and processing budgets are verified.

## M3-M5 source direction

1. M3 review decisions are separate hash-chained append-only events; approved/rejected are terminal in Alpha.
2. Big Bird jobs use `wwcx.cookie-monster.job.v1` with a dataset slug and deterministic idempotency key. Arbitrary filesystem paths/URLs/commands/credentials are not part of the handoff.
3. M4 Fengus execution is allowlisted and data-only. A hardened systemd unit denies network, archive/generated-store visibility and unbounded resources when later activated.
4. M5 ingestion read audit remains authoritative for source access; review decisions add human action evidence.
5. The UI shows review, Big Bird job and Fengus surfaces. Review buttons generate the exact bounded CLI action until authenticated web mutation transport is connected.

## Remaining activation work

1. Select and create a non-production staging dataset mapping on Edge1.
2. Package runtime status/review/job snapshots into the static Cookie Monster UI deployment path.
3. Decide/wire the authenticated operator transport for actual web approve/reject clicks.
4. Create the Fengus runtime user/directories and activate the hardened worker service only after deployment review.
5. Run M6 acceptance against the selected non-production staging dataset with zero provenance gaps and zero unauthorized writes.
