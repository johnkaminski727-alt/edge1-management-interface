# Cookie Monster Alpha

Last updated: 2026-08-22

## Verified implementation direction

- Branch: `agent/cookie-monster-alpha-foundation-ui-20260822`
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

## Next unblocked work after foundation review

1. Wire a non-production staging archive path on Edge1.
2. Add runtime status generation/deployment packaging for the static UI.
3. Define Big Bird -> Cookie Monster job envelope and idempotency key.
4. Implement Fengus worker isolation with no direct archive credentials.
5. Add bounded human approval state transition service and UI controls.
