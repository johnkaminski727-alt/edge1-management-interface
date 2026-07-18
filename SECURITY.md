# Security Policy

## Reporting a security concern

Please do not open a public issue containing credentials, private records, production data, internal addresses, detailed exploit steps, or unredacted diagnostic output.

Report concerns privately to the repository owner through an established trusted contact channel. Include only the minimum information needed to identify the affected component and reproduce the concern safely.

## Repository boundaries

The public repository must not contain:

- passwords, API keys, access tokens, or recovery codes
- private or preshared keys
- production databases, search indexes, or private documents
- personal information or audit contents
- unredacted configuration or raw sensitive diagnostics
- artifacts that provide unauthorized access to Edge1 or Big Bird services

Use sanitized examples and placeholder values in documentation and tests.

## Operational principles

- Prefer read-only diagnostics.
- Keep sensitive services localhost-bound or private-network-only.
- Require explicit operator control for approval, apply, restart, and rollback actions.
- Preserve audit trails and rollback paths.
- Validate configuration before restarting an affected service.
- Never commit secrets, even temporarily.

## Supported code

Security fixes are applied to the current default branch. Earlier snapshots may not receive separate fixes.
