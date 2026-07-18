# WW.CX Autonomous Operations Platform — Project Charter

## Status

Incubating architecture and implementation workstream inside `edge1-management-interface`.

## Purpose

Build a secure, authenticated, auditable operations layer that allows approved operators, AI assistants, and internal applications to inspect and maintain WW.CX infrastructure through explicit capabilities rather than unrestricted shell access.

## Initial scope

The first implementation milestone is read-only and includes:

- service and connector discovery;
- health and inventory reporting;
- capability enumeration;
- sanitized project and repository metadata;
- append-only audit events;
- request identifiers and structured errors;
- localhost or private-network deployment only.

Later milestones may add staged changes, validation, approval, apply, verification, and rollback. Write operations are out of scope until their policies, schemas, tests, and recovery procedures are accepted.

## Governing principles

1. Least privilege and explicit capability registration.
2. Read-only before write-enabled.
3. Staging and validation before application.
4. Verification before reporting completion.
5. Backups or rollback evidence before authoritative changes.
6. Redaction of credentials, tokens, private records, and sensitive diagnostics.
7. No arbitrary remote shell endpoint.
8. Every request receives an auditable identity, request ID, authorization decision, and result.
9. Production services remain allowlisted and independently health-checked.
10. Existing Edge1 and Big Bird controls are reused rather than bypassed.

## System boundary

The platform coordinates existing bounded systems, including:

- Edge1 Management Interface;
- Big Bird AI Gateway;
- Private Library search and import controls;
- the staged filesystem connector;
- GitHub repositories and release evidence;
- WW.CX Timekeeping;
- approved storage and DNS connectors.

It does not grant blanket operating-system authority and does not replace provider-native authentication or audit records.

## Initial capability families

- `operations.health.read`
- `operations.connectors.list`
- `operations.capabilities.list`
- `edge1.services.list`
- `edge1.service.status.read`
- `edge1.inventory.read`
- `library.collections.list`
- `library.search`
- `library.manifests.read`
- `github.repositories.read`
- `audit.events.read`

## Lifecycle model

```text
discover -> inspect -> propose -> stage -> validate -> approve -> apply -> verify -> record -> rollback if required
```

The initial milestone stops at `inspect` and `record`.

## Completion criteria for Milestone 1

- architecture and security boundaries are documented;
- capability and audit schemas exist;
- a read-only API contract is defined;
- all exposed operations are explicit and deny-by-default;
- tests cover schema validity, redaction, authorization rejection, and route behavior;
- deployment examples bind locally or to an approved private interface;
- no secrets or production records are committed.

## Repository strategy

This work begins in `edge1-management-interface` because that repository already contains the relevant read-only APIs, private-library integration, filesystem staging controls, service assets, registers, and validation framework. A dedicated repository may be split out after the shared contracts and first implementation are stable.
