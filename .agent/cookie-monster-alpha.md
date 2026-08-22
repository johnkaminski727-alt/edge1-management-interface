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
- Runtime cockpit publication is a separate atomic copy from generated evidence into an operator web root; generated state is never copied back into Git.
- Runtime dataset selection is slug-based and deterministic; neither Big Bird jobs nor the dataset registry may carry arbitrary archive/filesystem paths.
- Edge1 foundation installation is backup-first and leaves the staging dataset disabled; installation does not equal ingestion activation.
- Browser publication is derived and minimized by default; raw generated runtime evidence is not a browser contract.
- The shared Edge1 Operator registry may describe Cookie Monster as staged evidence, but navigation remains disabled until the real route and authorization boundary are accepted live.

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
- `config/edge1_operator/navigation_registry.json` (staged-disabled Cookie Monster candidate only)
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
- `docs/cookie-monster/alpha-operator-runbook.md`

## Closed review findings

Fen independently verified PR #512 and closed the M0-M2 source hardening review. Append-only provenance/idempotency, symlink containment and processing budgets are verified.

Fen independently verified PR #514 and PR #515 with no HIGH or MEDIUM findings. The M3-M6 review confirmed the Big Bird contract does not carry path/URL/command/credential authority, Fengus remains data-only and unactivated, review decisions are OS-level append-only/hash-chained, and the M6 gate independently recomputes provenance/review integrity.

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

The cockpit runtime-publication package is implemented source-side. It requires a valid generated `status.json`, validates every present JSON snapshot before mutation, keeps repository/generated/web roots disjoint, backs up the complete managed destination set, atomically publishes the UI plus runtime views, removes stale optional runtime state, emits a SHA-256 publication manifest and supports exact managed-file rollback.

PR #518 merged after the dedicated runtime-publication workflow, Edge1 Operator Validation and repository validation all passed. This closes the source implementation gap for runtime packaging. It does not claim a live Edge1 apply: the currently exposed Edge1 Operator connector remains read-only.

## M8 bounded dataset dispatch source package

The Big Bird -> Cookie Monster dispatcher is source-defined around a path-free runtime dataset registry. A job names only a bounded dataset slug; an enabled registry entry must explicitly be `non_production=true` and `read_only=true`. The dispatcher deterministically resolves `/srv/cookie-monster/datasets/<slug>`, rejects symlink escapes, uses dataset-specific generated output, reuses existing knowledge records for cross-run idempotency, rejects partial-pipeline semantics that Alpha does not yet implement, and records sanitized job failures without exception text.

PR #519 merged after the dedicated dataset-dispatch workflow, runtime-publication regression workflow, Edge1 Operator Validation and repository validation all passed. The example registry remains disabled by default and contains no path, URL, command or credential field. This is source readiness, not a live dataset activation.

## M9 Edge1 foundation installer source package

A backup-first source installer defines the exact private Edge1 foundation needed before a non-production activation: disabled runtime registry, `/srv/cookie-monster/datasets/alpha-staging`, generated-state root, Fengus inbox/outbox, dedicated nologin Fengus account, and the hardened worker template unit. Existing dataset registry divergence fails closed instead of being overwritten. Newly created staging is read-only by default, `systemctl daemon-reload` does not start a worker, and config rollback preserves runtime directories/service-account identity rather than deleting evidence or invalidating UIDs.

No live install is implied by repository source. The exposed Edge1 Operator connector remains read-only.

## M10 browser publication minimization hardening

A focused hardening follow-up keeps the runtime web surface from becoming a raw-evidence mirror. The publisher projects `wwcx.cookie-monster.operator-view.v1` JSON before writing to the web root.

Default publication is summary-only and excludes raw metadata payloads, metadata-tool filesystem paths, asset filenames/relative source locations, arbitrary acceptance detail strings, internal Fengus paths, raw knowledge facts and the generated evidence filesystem path. Explicit `--publish-detail` is bounded to `alpha-read-only` non-production staging evidence with zero unauthorized source writes, and even then raw metadata/tool paths stay excluded.

Static and runtime symlink sources fail closed. The runtime manifest hashes the published operator views rather than the raw generated snapshots.

## M11 operator-shell registration

Cookie Monster is represented in the canonical Edge1 Operator navigation registry as a `staged_disabled` candidate at `/edge1-status/cookie-monster/`. Its `browser_route` remains null, it is excluded from the navigation palette and ToolBox, and its authorization metadata is explicitly `unverified_route_policy`.

This makes the UI discoverable in the source architecture without pretending the live browser route, deployment state, or access-control boundary has been accepted. Promotion to `accepted_live` still requires real browser/auth acceptance evidence.

## Remaining activation work

1. Do not treat repository main as live Edge1 state: the latest read-only Edge1 snapshot still showed the management checkout at `20b3f6c2a5a3da6484b433f6f171c3c713ef920e`, behind the later runtime-publication/dispatch/foundation/UI-registration merges.
2. Reconcile/synchronize the intended Edge1 checkout through an authenticated write-capable deployment path before Cookie Monster publication or foundation apply.
3. Run the M9 installer preflight and reviewed `--apply` only through that authenticated write-capable Edge1 path; leave the staging dataset disabled after installation.
4. Populate one deliberately non-production `alpha-staging` dataset, then explicitly enable only that registry entry.
5. Run a bounded dispatch against staged data and verify source immutability, idempotency and provenance.
6. Publish only minimized operator-view snapshots and verify the browser route/access boundary before changing the staged operator-shell registration to `accepted_live`.
7. Keep web approve/reject clicks disabled until an authenticated operator mutation transport and human approval owner are deliberately defined.
8. Keep Fengus credential-free and runtime-inactive until a separate deployment review authorizes service activation; any later worker instance remains archive/network denied.
9. Re-run M6 against the deliberately selected Edge1 non-production staging dataset with zero provenance gaps and zero unauthorized writes.
