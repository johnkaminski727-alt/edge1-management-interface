# Edge1 Management Interface

[![Project status](https://img.shields.io/badge/status-active-2ea44f)](https://github.com/johnkaminski727-alt/edge1-management-interface)
[![Python](https://img.shields.io/badge/Python-3-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![ORCID](https://img.shields.io/badge/ORCID-0009--0000--9523--8529-A6CE39?logo=orcid&logoColor=white)](https://orcid.org/0009-0000-9523-8529)

A private-first management interface for Edge1 AI, digital-library, and infrastructure services.

The project combines responsive browser tools, narrow API wrappers, service diagnostics, operational documentation, and bounded automation. Its first production-oriented module is **Private Library Search**, an authenticated interface for searching the Big Bird operations collection with mobile-friendly results and source traceability.

> **Public-repository boundary:** buildable source and sanitized documentation belong here. Credentials, private records, production databases, search indexes, personal information, and unredacted diagnostics do not.

## Highlights

- Responsive desktop, tablet, and phone interface
- Read-only-first service design
- Private Library Search with source traceability
- Local Big Bird SQLite FTS5 integration
- Fixture fallback for offline validation
- Managed localhost-only service deployment
- Staged and audited filesystem-change proposals
- Operator-controlled approval, apply, and rollback boundaries
- Validation, smoke-test, handoff, and runbook assets

## Architecture at a glance

```text
Browser UI
    |
    v
Local read-only API wrapper
    |-- Big Bird SQLite FTS5 library engine
    |-- configured local HTTP backend
    `-- sanitized fixture fallback
```

See [the public project overview](docs/PUBLIC_OVERVIEW.md) for the project purpose, design principles, components, and repository map.

## Repository structure

```text
docs/       architecture, runbooks, decisions, and handoffs
src/api/    narrow API contracts and wrappers
src/web/    responsive browser interface
server/     local service entry points
tests/      validation and smoke tests
deploy/     deployment and service assets
tools/      diagnostics and operator utilities
registers/  project and completion registers
```

## Private Library Search

Run the local read-only UI and API wrapper:

```bash
python3 server/private_library_search_server.py --host 127.0.0.1 --port 8091
```

The browser client calls `/api/private-library/search`. The wrapper is localhost-only by default, clamps result limits, restricts access to the approved operations collection, and preserves fixture fallback behavior.

To discover a compatible local backend:

```bash
python3 tools/discover_private_library_backend.py
```

Then run with the generated configuration:

```bash
bin/run_private_library_search.sh 8091
```

When the local Big Bird library engine and database are available, successful direct responses use `mode: live_direct`.

## Static preview

The browser interface has no required build step:

```bash
python3 -m http.server 8088 --directory src/web
```

Then browse to `http://127.0.0.1:8088/` from the host or through an approved private tunnel.

## Validation

```bash
python3 tests/validate_static_ui.py
python3 tests/validate_search_service_assets.py
python3 -m json.tool src/api/private_library_search_contract.json >/dev/null
python3 -m json.tool src/web/private-library-search.fixture.json >/dev/null
```

## Managed service

Install and test the localhost-only search wrapper:

```bash
sudo deploy/install-private-library-search-service.sh
deploy/private-library-search-service-smoke-test.sh
```

Operator guidance is available in `docs/handoff/private-library-search-service-runbook.md`.

## AI Filesystem Connector

The connector follows a staged, human-controlled workflow:

```text
propose -> inspect -> validate -> approve/reject -> operator-controlled apply
```

AI-accessible capabilities remain limited to staging, status, diff, and audit functions. Approval, production application, restart, and rollback remain operator-controlled.

Key references:

- `docs/ai-filesystem-write-connector/phase18-final-completion-handoff.md`
- `docs/ai-filesystem-write-connector/phase-2-staged-proposal-intake.md`
- `docs/ai-filesystem-write-connector/phase-3-operator-approval-metadata.md`
- `docs/ai-filesystem-write-connector/phase-4-operator-controlled-apply.md`

## Security

Read [SECURITY.md](SECURITY.md) before reporting a vulnerability or contributing configuration examples. Never open a public issue containing credentials, production data, private records, or unredacted diagnostic output.

## Project records

The combined project register is maintained at:

```text
registers/combined-project-register-20260717.md
```

The autonomous-completion index is maintained at:

```text
docs/autonomous-completion/04-combined-register-index.md
```

## Maintainer

Created and maintained by **John Kaminski** through **Christmas Island Worldwide**.

- [ORCID: 0009-0000-9523-8529](https://orcid.org/0009-0000-9523-8529)
- [GitHub profile](https://github.com/johnkaminski727-alt)
