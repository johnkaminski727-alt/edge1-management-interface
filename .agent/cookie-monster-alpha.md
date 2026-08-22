# Cookie Monster Alpha

Last updated: 2026-08-22

## Verified implementation direction

- Alpha lives in `edge1-management-interface` as an isolated subsystem.
- Source input is read only; generated evidence must be outside the source tree.
- M0/M1 use synthetic/staging data, not canonical archive data.
- Operator UI is part of the deliverable, not deferred technical debt.
- Project mascot is an intentional first-class UI asset.
- Fengus remains disconnected in M0/M1 and has no archive credentials or direct archive authority.
- Human approval is visible as a queue but no approval mutation endpoint exists yet.

## Implemented surfaces

- `server/cookie_monster_alpha.py`
- `tests/test_cookie_monster_alpha.py`
- `src/web/cookie-monster/index.html`
- `src/web/cookie-monster/demo-status.json`
- `src/web/cookie-monster/assets/mascot.webp`
- `docs/cookie-monster/alpha-foundation.md`

## 2026-08-22 independent-review hardening

Fen independently reviewed merged PR #506 and identified one HIGH provenance issue plus two MEDIUM staging/runtime issues. The follow-up source hardening now addresses all three:

1. Knowledge and audit JSONL are append-only across runs; unchanged assets reuse prior knowledge records through deterministic idempotency keys instead of generating new unlinked UUID records.
2. Discovery fails closed on symlink files/directories and verifies every resolved path remains under the staging source root.
3. Metadata extraction has an aggregate per-file time budget and each run has a total time budget.

Regression coverage expanded from 6 to 11 tests, including repeat-run idempotency/audit preservation, legacy-record reuse, symlink escape rejection and budget enforcement.

## Remaining work after hardening review

1. Wire a non-production staging archive path on Edge1.
2. Add runtime status generation/deployment packaging for the static UI.
3. Define Big Bird -> Cookie Monster job envelope and idempotency key.
4. Implement Fengus worker isolation with no direct archive credentials.
5. Add bounded human approval state transition service and UI controls.
6. Resolve the still-open human/authority decisions for the concrete archive target, staging dataset, runtime credentials and approval ownership before moving beyond demo/local-fixture Alpha.
