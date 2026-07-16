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
- `src/api/private_library_search_contract.json`
- `src/web/private-library-search.fixture.json`

