# Edge1 candidate configuration workspace G1

**Status:** isolated GitHub development prototype; not installed or published. This branch starts from main `723e712775da5534042a146a725fa63a9da39421`, independently of draft Spamhaus PR #607.

## Intended operator journey

The approved Edge1 direction combines a stable operations shell and contextual ToolBox with disciplined running/candidate configuration. G1 creates the shared primitives before authorizing any real infrastructure edits.

1. **Observe:** view the running configuration snapshot and evidence timestamp. The running snapshot MUST come from a separately authorized, read-only source; the prototype uses static demo settings only.
2. **Propose:** create a local candidate overlay pinned to the immutable base-revision SHA-256. Validation rejects unknown fields, unsupported types, duplicate panels and out-of-range settings. No credentials, addresses, arbitrary commands or secrets are accepted.
3. **Review:** show validation status, exact changed paths, machine-readable before/after values and a human-readable unified diff. Pending changes remain visible until discarded or an eventual separately approved apply.
4. **Detect drift:** if running state differs from the candidate's base revision, stop and require an explicit rebase/review; do not overwrite external changes.
5. **Discard:** revert candidate to the unchanged running snapshot and record a candidate-only audit event.
6. **Future apply:** *not implemented*. Any eventual apply must be separately authorized through the existing repository-reviewed `tools/safe_change_runner.py` registry. The production registry currently contains no allowed operations; do not add generic shell execution or treat a preview as deploy approval.

## G1 reference model and contract

`tools/operations/edge1_candidate_workspace.py` is a pure Python state model. Its settings schema includes **only display preferences**, not server state:

| Section | G1 settings |
|---|---|
| dashboard | refresh_seconds (10–3600), unique panels from system/services/security/network/jobs |
| inventory | show_interfaces, show_routes, show_vpn_peers (strict booleans) |
| alerts | show_warnings (strict boolean), max_items (1–48) |

`Workspace.preview()` returns a dictionary with schema name, base/candidate revisions, pending flag, validation result, `execution_allowed: false`, exact changed paths and unified diff. `propose(..., expected_revision=...)` rejects mismatched base revisions. `discard` reverts local candidate changes. `rebase_running` refuses to silently discard pending changes after a running-configuration change.

The event list is **in-memory diagnostic context only**. It is not durable audit history, an authenticated identity record, a live source of truth or production security evidence. Candidate revision hashes detect ordinary mismatches but are not authorization tokens.

## Planned API contracts (design, not deployed)

- `GET /api/v1/config/workspaces/{workspace_id}`: authenticated, authorized **read-only** summary and current revision, populated from a freshness-checked running snapshot.
- `POST /api/v1/config/workspaces/{workspace_id}/candidate`: authenticated, CSRF-protected proposal with `expected_base_revision` and one schema-allowed typed field. Returns validated candidate state and diff; no application or server mutation.
- `POST /api/v1/config/workspaces/{workspace_id}/discard`: authenticated candidate discard with exact revision precondition.
- `POST /api/v1/config/workspaces/{workspace_id}/validate`: idempotent candidate validation and dry-run policy checks; no live changes.
- `POST /api/v1/config/workspaces/{workspace_id}/apply`: **NOT PRESENT IN G1**; future separate approval, least-privilege apply job, replay resistance, rollback checkpoint and externally verifiable post-apply checks.

No route above is implemented or exposed by this prototype. A future authenticated API must enforce server-side authorization, input-size limits, tenant isolation, immutable audit persistence and a fresh compare-and-swap revision precondition; never trust UI state alone.

## Operations Center and contextual ToolBox integration

Use the existing `src/web/operations-center/index.html`, `core-dashboard.js`, the read-only `core-status.json` observation and the existing operator shell. Do not duplicate status collectors or assume stale/unavailable observations are healthy. The first UI deliverable is an **unpublished, self-contained local preview** showing running/candidate settings, typed display controls, pending-change summary and a read-only contextual ToolBox for the selected section.

The ToolBox should link to existing health, networking and security observability sections and provide explainers and validation checks; it must not expose production mutation actions. Keep any live authenticated API and server changes behind separate design, permission and deployment reviews.

## Test and release gates

Run `python3 tests/validate_edge1_candidate_workspace.py -v`. Negative cases include wrong type, unknown setting, duplicate panels, stale candidate revision, externally changed running state and mutation of caller-owned snapshots. HTML preview uses no server endpoint or persistent storage. Repository CI is required on the final branch; isolated tests are not proof of a production deployment. No GitHub merge, production installation, public publication, unit enablement, reboot or firewall modification is included in G1.
