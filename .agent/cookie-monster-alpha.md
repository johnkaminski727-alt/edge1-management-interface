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
- Runtime dataset selection is slug-based and deterministic; neither Big Bird jobs nor the dataset registry may carry arbitrary archive/filesystem paths.
- Edge1 foundation installation is backup-first and leaves the staging dataset disabled; installation does not equal ingestion activation.

## Implemented surfaces

- `server/cookie_monster_alpha.py`
- `server/cookie_monster_contract.py`
- `server/cookie_monster_dispatch.py`
- `server/cookie_monster_review.py`
- `server/cookie_monster_fengus_worker.py`
- `server/cookie_monster_acceptance.py`
- `deploy/cookie-monster-fengus-worker@.service`
- `deploy/cookie_monster_runtime_publish.py`
- `deploy/cookie_monster_edge1_install.py`
- `config/cookie-monster/datasets.example.json`
- `tests/test_cookie_monster_alpha.py`
- `tests/test_cookie_monster_control.py`
- `tests/test_cookie_monster_dispatch.py`
- `tests/test_cookie_monster_acceptance.py`
- `tests/test_cookie_monster_runtime_publish.py`
- `tests/test_cookie_monster_edge1_install.py`
- `src/web/cookie-monster/index.html`
- `src/web/cookie-monster/demo-status.json`
- `src/web/cookie-monster/assets/mascot.webp`
- `docs/cookie-monster/alpha-foundation.md`
- `docs/cookie-monster/alpha-m3-m5.md`
- `docs/cookie-monster/alpha-m6-acceptance.md`
- `docs/cookie-monster/alpha-dispatch.md`
- `docs/cookie-monster/runtime-publication.md`
- `docs/cookie-monster/edge1-foundation-install.md`

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

PR #518 merged after the dedicated runtime-publication workflow, Edge1 Operator Validation and repository validation all passed. This closes the source implementation gap for runtime packaging. It does not claim a live Edge1 apply: the currently exposed Edge1 Operator connector remains read-only.

## M8 bounded dataset dispatch source package

The Big Bird -> Cookie Monster dispatcher is source-defined around a path-free runtime dataset registry. A job names only a bounded dataset slug; an enabled registry entry must explicitly be `non_production=true` and `read_only=true`. The dispatcher deterministically resolves `/srv/cookie-monster/datasets/<slug>`, rejects symlink escapes, uses dataset-specific generated output, reuses existing knowledge records for cross-run idempotency, rejects partial-pipeline semantics that Alpha does not yet implement, and records sanitized job failures without exception text.

PR #519 merged after the dedicated dataset-dispatch workflow, runtime-publication regression workflow, Edge1 Operator Validation and repository validation all passed. The example registry remains disabled by default and contains no path, URL, command or credential field. This is source readiness, not a live dataset activation.

## M9 Edge1 foundation installer source package

A backup-first source installer now defines the exact private Edge1 foundation needed before a non-production activation: disabled runtime registry, `/srv/cookie-monster/datasets/alpha-staging`, generated-state root, Fengus inbox/outbox, dedicated nologin Fengus account, and the hardened worker template unit. Existing dataset registry divergence fails closed instead of being overwritten. Newly created staging is read-only by default, `systemctl daemon-reload` does not start a worker, and config rollback preserves runtime directories/service-account identity rather than deleting evidence or invalidating UIDs.

Local source validation before publication: Python compile PASS and 7/7 targeted installer tests PASS. Dedicated CI and repository validation remain required before merge. No live install has been performed because the exposed Edge1 Operator connector is read-only.

## Remaining activation work

1. Run the M9 installer preflight and reviewed `--apply` through an authenticated write-capable Edge1 path.
2. Populate the deliberately non-production `alpha-staging` directory, then explicitly enable only that registry entry.
3. Run a bounded dispatch against staged data and verify source immutability, idempotency and provenance.
4. Publish that dataset's generated runtime snapshots through the PR #518 publisher and verify the private cockpit.
5. Decide/wire the authenticated operator transport for actual web approve/reject clicks.
6. Exercise a Fengus template instance only with a bounded generated work item after runtime review; keep archive/network access denied.
7. Re-run M6 against the deliberately selected Edge1 non-production staging dataset with zero provenance gaps and zero unauthorized writes.
