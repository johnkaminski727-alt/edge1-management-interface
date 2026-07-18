# Contributing to Edge1 Management Interface

Thank you for helping improve the Edge1 Management Interface.

This repository is public, but the systems it documents and supports are private-first. Contributions must preserve that boundary.

## Before you begin

- Read `SECURITY.md`.
- Do not include credentials, tokens, private records, production databases, search indexes, personal information, or unredacted logs.
- Use sanitized examples and synthetic fixtures.
- Keep services localhost-only by default unless a change explicitly documents and tests a stronger access boundary.
- Prefer small, reversible changes with clear validation steps.

## Development workflow

1. Create a focused branch from `main`.
2. Make one coherent change at a time.
3. Add or update tests and documentation.
4. Run the relevant validation commands.
5. Open a pull request describing the purpose, security impact, validation performed, and rollback path.

## Validation

Run the checks relevant to your change. The common baseline is:

```bash
python3 tests/validate_static_ui.py
python3 tests/validate_search_service_assets.py
python3 tests/validate_time_authority.py
python3 -m json.tool src/api/private_library_search_contract.json >/dev/null
python3 -m json.tool src/api/time_authority_contract.json >/dev/null
python3 -m json.tool src/web/private-library-search.fixture.json >/dev/null
```

When a validation script is not applicable, explain why in the pull request.

## Pull request expectations

A good pull request includes:

- a concise problem statement;
- the proposed change;
- affected components;
- privacy and security considerations;
- commands used for validation;
- deployment notes, if any;
- a rollback or reversal path.

## Documentation standards

Public documentation should explain architecture and operator intent without exposing sensitive deployment details. Use placeholders for hostnames, addresses, usernames, filesystem paths, and configuration values unless they are already intentionally public and safe.

## Operational changes

Changes involving service installation, restart, production configuration, data migration, approval controls, or filesystem writes require an explicit operator-controlled step. Automation may prepare and validate those changes, but it must not silently bypass the documented approval boundary.

## Reporting security issues

Do not open a public issue for a vulnerability or sensitive exposure. Follow the private reporting instructions in `SECURITY.md`.
