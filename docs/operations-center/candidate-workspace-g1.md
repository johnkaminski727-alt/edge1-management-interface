# Edge1 candidate configuration workspace G1

**Status:** local-only preview installation prepared; no production application capability. No Edge1 installation can be claimed until the operator executes the pinned installer and supplies successful verification output. This branch starts from main `723e712775da5534042a146a725fa63a9da39421`, independently of draft Spamhaus PR #607.

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

## Local-only G1 installation and access

The `deploy/candidate-workspace/install-preview.sh` script installs **only** static HTML, the pure Python candidate model, this README and regression tests into `/opt/edge1-candidate-workspace-g1`. It defaults to `--check`, accepts `--apply` only with root privileges, rejects symlinked source files and unrecognized existing destinations, checks the candidate regression tests and records SHA-256 payload hashes. On later authorized updates it backs up its own previously marked installation under `/var/backups/edge1-candidate-workspace-g1`. `--verify` checks the installed payload. This package does **not** modify the existing `/var/www/edge1-status` site, install systemd units, open a network port, modify a firewall or create an authenticated API.

For a one-session private preview, an operator may start a separate loopback-only Python static server on Edge1 with `python3 -m http.server 8766 --bind 127.0.0.1 --directory /opt/edge1-candidate-workspace-g1`, then independently connect from Windows with `ssh -L 8766:127.0.0.1:8766 edge1` and open `http://127.0.0.1:8766/` in that Windows browser. Keep the Edge1 serving process and Windows SSH tunnel open only while reviewing the prototype. Stop the server with Ctrl+C. No systemd persistence is configured. The ToolBox in this standalone preview links to GitHub documentation instead of assuming live Operations Center routes are reachable from the local-only port.

The browser model and Python engine are **two independently tested prototypes**, not yet connected to each other or to live settings. Changes made in the preview exist only in that browser tab, with no server persistence. The preview itself provides only static demonstration values, not a live Edge1 status report.

## Edge1 operator installation evidence — September 27, 2026

The operator retrieved the exact reviewed source revision `e7bd4b896b6c305e4b4730c3fbadbe8c54e8df25` on Edge1 using `git fetch` and `git archive`, without switching the production repository branch. The `--check` preflight passed eight Python regression tests and verified that the static HTML contains no network requests or live Apply control. The opt-in `--apply` installer repeated those checks and installed the isolated preview under `/opt/edge1-candidate-workspace-g1`; `--verify` confirmed the installed SHA-256 manifest and Python syntax. The operator's interactive SSH session remained open, and the installer reported no changes to existing production services. **Installation is verified**, but browser access, loopback-only preview serving, authenticated API integration and any live configuration application have not been verified. The HTML and Python model remain separate prototypes.

## Test and release gates

Run `python3 tests/validate_edge1_candidate_workspace.py -v`. Negative cases include wrong type, unknown setting, duplicate panels, stale candidate revision, externally changed running state and mutation of caller-owned snapshots. HTML preview uses no server endpoint or persistent storage. Repository CI is required on the final branch; isolated tests are not proof of a production deployment. No GitHub merge, production installation, public publication, unit enablement, reboot or firewall modification is included in G1.
