# Edge1 Management Interface

[![Project status](https://img.shields.io/badge/status-active-2ea44f)](https://github.com/johnkaminski727-alt/edge1-management-interface)
[![Validate repository](https://github.com/johnkaminski727-alt/edge1-management-interface/actions/workflows/validate.yml/badge.svg)](https://github.com/johnkaminski727-alt/edge1-management-interface/actions/workflows/validate.yml)
[![Python](https://img.shields.io/badge/Python-3-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![ORCID](https://img.shields.io/badge/ORCID-0009--0000--9523--8529-A6CE39?logo=orcid&logoColor=white)](https://orcid.org/0009-0000-9523-8529)

A private-first management interface for Edge1 AI, digital-library, communications, time-authority, and infrastructure services.

The project combines responsive browser tools, narrow API wrappers, service diagnostics, operational documentation, bounded automation, and evidence-backed deployment workflows.

> **Public-repository boundary:** buildable source and sanitized documentation belong here. Credentials, private records, production databases, search indexes, personal information, and unredacted diagnostics do not.

## Highlights

- Responsive desktop, tablet, and phone interface
- Read-only-first service design
- Private Library Search with source traceability
- Local Big Bird SQLite FTS5 integration
- Private Edge1 IRC/NNTP Communications Relay
- Selective outbound TLS NNTP reader ingestion with explicit provenance
- Private read-only NNTP News Reader with source filters and threaded views
- Dual-observer WW.CX Time Authority monitoring
- Staged and audited filesystem-change proposals
- Operator-controlled approval, apply, rollback, evidence, and archive boundaries
- Validation, smoke-test, handoff, and runbook assets

## Architecture at a glance

```text
Private browser/operator tools
    |
    +-- Private Library Search -> Big Bird SQLite / local backend
    +-- Communications Relay UI -> loopback control API -> IRC / NNTP / SQLite
    +-- Time Authority UI/API -> read-only NTP observations
    `-- staged filesystem / operational tooling
```

See [the public project overview](docs/PUBLIC_OVERVIEW.md) for the project purpose, design principles, components, and repository map.

## Repository structure

```text
docs/       architecture, runbooks, decisions, acceptance, archive, and handoffs
src/api/    narrow API contracts and wrappers
src/web/    responsive browser interfaces
server/     local service entry points
tests/      validation and smoke tests
deploy/     deployment and service assets
tools/      diagnostics and operator utilities
registers/  project and completion registers
.agent/     durable sanitized workstream state
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

## Communications Relay

The accepted Edge1 Communications Relay is a private-first IRC and NNTP service with durable SQLite storage, local identity/moderation, automatic ingestion, and a loopback read-only control surface.

Accepted private listener baseline:

```text
127.0.0.1:16667  IRC
127.0.0.1:1119   NNTP
127.0.0.1:8100   control/API/News Reader
```

Accepted selective Eternal September reader mappings:

- `comp.lang.python` -> `usenet.comp.lang.python`;
- `news.admin.peering` -> `usenet.news.admin.peering`.

These are outbound TLS reader pulls from `news.eternal-september.org:563`, not formal peering. Upstream posting, inbound feeds, streaming federation, public IRC/NNTP exposure, and forwarding private `wwcx.*` articles upstream remain disabled or separately gated.

The private News Reader v2 supports bounded search, exact source filters, 25/50/100 pagination, article detail/provenance, and threaded/flat views using stored reference ancestry. Web mutation methods remain blocked.

Start with:

- `docs/communications/README.md`;
- `docs/handoff/edge1-comms-relay-runbook.md`;
- `.agent/comms-relay.md`;
- `.agent/comms-relay-upstream-nntp.md`.

The sanitized closeout/archive-preparation record is `docs/archive/edge1-comms-relay-news-reader-closeout-20260817.md`.

## Static preview

The browser interfaces have no required build step:

```bash
python3 -m http.server 8088 --directory src/web
```

Browse from the host or through an approved private tunnel. Static preview is not a substitute for the authenticated/live service boundary.

## WW.CX Time Authority

The Time Authority package records read-only NTP measurements from Edge1 and the WW.CX shared host. It tracks public source names, resolved addresses, stratum, reference ID, RTT, estimated offset, dispersion, reachability, and expected-source conformance without changing either server clock.

```bash
python3 tests/validate_time_authority.py
python3 tests/validate_time_authority_collector_compat.py
python3 tests/validate_time_authority_rollout_simulation.py
python3 server/time_authority_server.py --host 127.0.0.1 --port 8101
```

Deployment profiles, source registers, baseline observations, preflight checks, smoke tests, systemd units, automatic shared-host cron tooling, and spreadsheet-ready CSV export are documented in `docs/handoff/time-authority-runbook.md`.

## Validation

Representative repository checks include:

```bash
python3 tests/validate_static_ui.py
python3 tests/validate_search_service_assets.py
python3 tests/validate_comms_relay.py
python3 tests/validate_comms_ingestion.py
python3 tests/validate_comms_upstream_nntp.py
python3 tests/validate_comms_news_reader.py
python3 tests/validate_time_authority.py
python3 tests/validate_time_authority_collector_compat.py
python3 tests/validate_records_evidence.py
python3 tests/validate_records_evidence_automation.py
python3 -m json.tool src/api/private_library_search_contract.json >/dev/null
python3 -m json.tool src/api/time_authority_contract.json >/dev/null
python3 -m json.tool src/web/private-library-search.fixture.json >/dev/null
```

Use workstream-specific runbooks for production validation and live acceptance; passing repository tests alone does not authorize deployment.

## Managed service

Install and test the localhost-only Private Library Search wrapper:

```bash
sudo deploy/install-private-library-search-service.sh
deploy/private-library-search-service-smoke-test.sh
```

Operator guidance is available in `docs/handoff/private-library-search-service-runbook.md`.

Communications Relay operational guidance is in `docs/handoff/edge1-comms-relay-runbook.md`.

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

Read [SECURITY.md](SECURITY.md) before reporting a vulnerability or contributing configuration examples. Never open a public issue containing credentials, production data, private records, production databases, or unredacted diagnostic output.

## Project records

The current combined project register is maintained at:

```text
registers/combined-project-register-20260719.md
```

The autonomous-completion index is maintained at:

```text
docs/autonomous-completion/04-combined-register-index.md
```

Workstream-specific current state is also maintained under `.agent/`.

## Records governance

The repository uses a project-defined records-and-evidence control to keep engineering claims traceable without overstating certification or publishing private operational data.

- [Records and Evidence Policy](docs/records-governance/RECORDS_EVIDENCE_POLICY.md)
- [Repository Evidence Map](docs/records-governance/EVIDENCE_MAP.md)
- [Operational Records Evidence Program](docs/records-management/06-operational-evidence-program.md)
- [Records Evidence Schema](schemas/records-evidence.schema.json)
- [Sanitized Evidence Package](examples/records-evidence/)
- [Repository Evidence Quality Index](docs/records-management/07-repository-quality-index.md)
- [Automated repository validation](.github/workflows/validate.yml)

## Maintainer

Created and maintained by **John Kaminski** through **Christmas Island Worldwide**.

- [ORCID: 0009-0000-9523-8529](https://orcid.org/0009-0000-9523-8529)
- [GitHub profile](https://github.com/johnkaminski727-alt)
