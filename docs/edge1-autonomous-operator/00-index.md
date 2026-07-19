# Edge1 Autonomous Operator

This directory defines the repository-backed plan and control surface for a persistent authenticated Edge1 operator available to ChatGPT through a private MCP connection.

## Goals

- Remove repeated SSH, passphrase, command-relay, and output-relay work.
- Provide broad Edge1 interoperability through structured tools plus audited bounded shell execution.
- Preserve standing authority for routine, reversible engineering work.
- Require fresh approval only at material legal, financial, credential, irreversible, emergency-calling, number-porting, or production-traffic boundaries.
- Preserve auditability, rollback, secret redaction, and truthful reporting.

## Documents

- `01-architecture.md` — service, identity, transport, privilege, audit, and reliability architecture.
- `02-authority-and-risk-policy.md` — standing authorization and stop boundaries.
- `03-mcp-tool-contract.md` — proposed MCP tool surface and response schema.
- `04-implementation-plan.md` — phased build, validation, deployment, and integration plan.
- `05-acceptance-checklist.md` — definition of done and test scenarios.

## Repository placement

The implementation belongs in this repository because it already contains the Edge1 management interface, filesystem connector, deployment assets, tests, runbooks, evidence controls, and localhost-only service patterns. Runtime credentials, private configuration, audit records, and production evidence must remain outside Git.

## Status

Initial specification and implementation scaffold. No production listener, privilege policy, or connector credentials are introduced by this documentation change.
