# Architecture and Security Boundary

## Architecture

```text
Approved client
    |
    v
WW.CX Operations API
    |-- authentication and replay protection
    |-- policy and capability evaluation
    |-- request validation and redaction
    |-- append-only audit event creation
    `-- connector routing
          |-- Edge1 read-only inventory
          |-- Big Bird service health
          |-- Private Library search and manifests
          |-- GitHub repository metadata
          `-- future staged-operation adapters
```

## Trust boundaries

### Client boundary

Clients authenticate using scoped credentials and signed requests. Caller identity is never inferred from request content.

### API boundary

The API validates schemas, timestamps, nonces, scopes, resource identifiers, and request sizes before dispatch. Unknown capabilities and connectors are denied.

### Connector boundary

Connectors expose typed operations. They do not accept arbitrary command strings, arbitrary SQL, unrestricted file paths, or unregistered service names.

### Production boundary

Production credentials and authoritative data remain outside source control. Connector service accounts receive only the permissions necessary for registered capabilities.

## Initial deployment constraints

- Bind to localhost or an approved private management interface.
- Use a dedicated unprivileged service account.
- Store configuration under `/etc/wwcx-operations`.
- Store runtime state under `/var/lib/wwcx-operations`.
- Store logs under `/var/log/wwcx-operations`.
- Store rollback assets under `/var/backups/wwcx-operations`.
- Reject write operations in the first milestone.

## Authentication baseline

The implementation should reuse the established Big Bird request-signing pattern where practical:

- key identifier;
- timestamp with a narrow acceptance window;
- nonce persisted for replay rejection;
- request-body hash;
- signature over canonical request material;
- scoped authorization attached to the authenticated principal.

## Authorization model

Roles map to capabilities; roles do not imply blanket connector access.

Initial roles:

- `observer`
- `internal_viewer`
- `documentation_editor`
- `operations_stager`
- `operations_approver`
- `service_operator`
- `repository_maintainer`
- `administrator`

The Milestone 1 service enables only read capabilities for `observer` and `internal_viewer`.

## Explicitly prohibited initial operations

- arbitrary shell execution;
- arbitrary filesystem writes;
- production database mutation;
- service restart;
- DNS mutation;
- credential rotation;
- user or SSH access changes;
- firewall changes;
- deletion of authoritative records;
- force pushes or history rewrites.

## Audit requirements

Every request records:

- event and request identifiers;
- UTC timestamp;
- authenticated actor and key identifier;
- requested capability and connector;
- sanitized parameters;
- authorization decision;
- outcome and status;
- affected resource identifiers;
- verification state;
- duration and error classification.

Secrets and private document contents must not appear in ordinary audit events.

## Failure behavior

- Deny unknown capabilities and resources.
- Fail closed when policy or identity cannot be resolved.
- Return structured errors without stack traces or secrets.
- Preserve an audit event for rejected and failed requests.
- Distinguish `blocked`, `failed`, `not_supported`, and `unauthorized`.

## Evolution rule

A write capability may be enabled only when it has:

1. a registered capability identifier;
2. an input and result schema;
3. policy mapping;
4. validation and dry-run behavior;
5. audit coverage;
6. backup or rollback behavior;
7. integration and security tests;
8. an operator runbook.
