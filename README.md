# Edge1 Management Interface

Read-only first management interface for Edge1.

## Current Goal

Build the Private Library Search module as the first realistic website module:

- private/VPN-only access
- authenticated operator session
- read-only search against the Edge1 `operations` collection
- desktop/tablet/phone responsive layouts
- mobile card results instead of wide tables
- source traceability for every result

## Boundaries

This repo must not contain:

- passwords
- API keys
- private keys
- WireGuard private keys or preshared keys
- session tokens
- recovery codes
- raw sensitive diagnostics
- large binary archives

Large byte-preservation artifacts belong in the Edge1 companion file archive.
Operational knowledge belongs in the Edge1 private library.
Buildable source belongs here.

## Initial Structure

```text
docs/       design notes, implementation plans, acceptance criteria
src/api/    narrow read-only API wrappers
src/web/    browser UI modules
tests/      fixtures and test scaffolding
deploy/     deployment notes and scripts
registers/ source-control-friendly registers
```

## First Module

See:

- `docs/private-library-search-module.md`
- `docs/mobile-responsive-rules.md`
- `src/web/index.html`
- `src/web/app.js`
- `src/web/styles.css`
- `src/api/private_library_search_contract.json`
- `src/web/private-library-search.fixture.json`

## Local Static Preview

The first UI pass has no build step. Open `src/web/index.html` in a browser or serve the repo with a simple static server.

```bash
cd /opt/edge1-management-interface
python3 -m http.server 8088 --directory src/web
```

Then browse to `http://127.0.0.1:8088/` from the host or through an approved private tunnel.

## Validation

```bash
python3 tests/validate_static_ui.py
python3 -m json.tool src/api/private_library_search_contract.json >/dev/null
python3 -m json.tool src/web/private-library-search.fixture.json >/dev/null
```

## Local Private Library Search API

Run the read-only private library search UI and API wrapper locally:

```bash
python3 server/private_library_search_server.py --host 127.0.0.1 --port 8091
```

The browser client calls `/api/private-library/search`. The wrapper is
localhost-only by default, clamps result limits, and only allows the
`operations` collection. If `EDGE1_LIBRARY_SEARCH_URL` is set, the wrapper
forwards searches to that backend; otherwise it returns fixture-backed results.

## Live Private Library Backend

Discover a compatible local read-only library search backend:

```bash
python3 tools/discover_private_library_backend.py
```

If discovery succeeds, run the UI/API wrapper with the generated config:

```bash
bin/run_private_library_search.sh 8091
```

The wrapper supports GET and POST JSON backends through
`config/private-library-search.env` while preserving fixture fallback behavior.

## Direct Private Library Search

The local search wrapper first tries Big Bird's read-only SQLite FTS5 library
engine directly:

```bash
bin/run_private_library_search.sh 8091
```

The direct bridge uses `/opt/bigbird-ai-gateway/app/library_engine.py` and
`/var/lib/bigbird-ai-library/library.sqlite3` by default. Successful direct
responses use `"mode": "live_direct"`. If the engine or DB is unavailable, the
wrapper preserves the existing HTTP-backend and fixture fallback behavior.

## Handoff Status

Current handoff materials live under `docs/handoff/`.

The Private Library Search module is wired to the local read-only Big Bird
library engine and returns `mode: live_direct` when the SQLite library database
is readable by the wrapper process. Fixture fallback remains available for
offline validation.

## Autonomous Completion

Project controls for autonomous completion live under
`docs/autonomous-completion/`. The master register is
`registers/autonomous-completion-register-20260717.md`.

Run the read-only verifier at any handoff point:

```bash
python3 tools/handoff/verify_handoff_state.py
```

## Combined Registers

The project-wide combined register is:

```text
registers/combined-project-register-20260717.md
```

The combined register index is:

```text
docs/autonomous-completion/04-combined-register-index.md
```

## AI Filesystem Connector Status

The AI Filesystem Connector is complete for Phase 1 docs-only production use.

Key references:

- docs/ai-filesystem-write-connector/phase18-final-completion-handoff.md
- docs/ai-filesystem-write-connector/phase16-operational-validation-handoff.md
- docs/registers/ai-filesystem-connector-register-20260717.md
- docs/handoffs/NEW-CHAT-AI-FILESYSTEM-CONNECTOR.md

Safety boundary: MCP can stage docs-only proposals and read status/diff/audit. Approval, apply, and rollback remain operator/root-only.
