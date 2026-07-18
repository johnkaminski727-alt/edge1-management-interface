# Edge1 Management Interface — Public Overview

Edge1 Management Interface is an operator-focused control surface for privately hosted AI and digital-library services.

## Purpose

The project brings together a responsive browser interface, narrow read-only API wrappers, service diagnostics, operational documentation, and carefully bounded automation for the Edge1 environment.

Its first production-oriented module is Private Library Search: an authenticated, private-network interface for searching the Big Bird operations collection with source traceability and mobile-friendly results.

## Design principles

- Read-only capabilities come first.
- Sensitive services remain private-network or localhost bound.
- Every result should retain source traceability.
- Automation must be bounded, reversible, and auditable.
- Credentials, private records, raw diagnostics, and production data do not belong in the public repository.
- Browser experiences should work on desktop, tablet, and phone.

## Major components

### Private Library Search

A responsive search interface and local API wrapper with result limits, collection allowlisting, fixture fallback, and support for the Big Bird SQLite FTS5 library engine.

### AI Filesystem Connector

A staged, operator-controlled workflow for proposing and reviewing documentation changes. Approval and production application remain human-controlled and audited.

### Service operations

Deployment assets, smoke tests, runbooks, and handoff documentation for managed Edge1 services.

### Network safeguards

Operational tooling and documentation for controlled network filtering and rollback procedures.

## Repository map

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

## Safety boundary

This repository contains buildable source and sanitized documentation. It must not contain passwords, API keys, private keys, session tokens, recovery codes, private documents, production databases, search indexes, or unredacted diagnostic output.

## Project identity

Created and maintained by John Kaminski through Christmas Island Worldwide.

- ORCID: https://orcid.org/0009-0000-9523-8529
- GitHub: https://github.com/johnkaminski727-alt
