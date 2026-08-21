# BigBird Edge1 Control Plane v2

Status: design / source-only foundation
Tracking: #498

## Decision

Replace the legacy `bigbird-edge1-connector` lifecycle client with a capability-based control plane. Do not convert the legacy client into an unrestricted read/write agent.

The replacement reuses two existing trusted building blocks:

1. **Edge1 Operations API** for signed, audited, fixed privileged actions.
2. **AI Filesystem Write Connector** for staged, diffable, preconditioned, reversible filesystem writes.

The BigBird Control Plane is the policy and orchestration layer above those components. It exposes typed capabilities to Big Bird while preserving independent authorization for read, staged-write, apply, deploy, and privileged-service operations.

## Goals

- Broad but bounded read access across approved Edge1 operational surfaces.
- Controlled write access without arbitrary shell or arbitrary path access.
- Per-capability authorization rather than a single global read/write switch.
- Typed inputs validated server-side.
- Idempotency, preconditions, verification, rollback, and audit for mutations.
- Compatibility with Big Bird/MCP tool discovery.
- No secrets in Git, audit output, tool results, or prompts.
- Gradual migration with the legacy connector retained only until parity is demonstrated.

## Non-goals

- Arbitrary root shell.
- Arbitrary `sudo`.
- Arbitrary SQL.
- Arbitrary filesystem access.
- Arbitrary systemd control.
- Direct mutation of firewall, DNS, VPN, credential, identity, or security-sensitive configuration without a dedicated reviewed capability.
- One global `write_enabled` flag that unlocks all mutation classes.

## Planes

### Read plane

Read capabilities are normally available without operator approval after authentication and scope checks, but remain bounded by action, root, schema, timeout, and output limits.

Initial families:

- `edge1.status.*`
- `edge1.repository.read.*`
- `edge1.files.read.*`
- `edge1.logs.read.*`
- `edge1.library.read.*`
- `edge1.archive.read.*`
- `edge1.service.read.*`
- `edge1.database.read.*` through dedicated adapters only

### Staged-write plane

Writes that can be represented as a candidate change use a transaction-like lifecycle:

```text
propose
  -> stage
  -> validate
  -> inspect/diff
  -> authorize
  -> apply
  -> verify
  -> commit evidence
  -> rollback when required
```

A staged mutation carries:

- stable request ID
- actor and correlation ID
- capability name/version
- target identifier
- expected current revision/digest
- proposed content/change
- validation result
- generated diff
- expiration
- idempotency key
- backup/rollback metadata
- final verification result

The existing AI Filesystem Write Connector is the initial filesystem implementation of this plane.

### Privileged action plane

The Edge1 Operations API remains the privileged execution broker for fixed actions. The broker must continue to reject arbitrary argv and arbitrary paths.

Each action has:

- capability name
- input schema
- mutation classification
- required scope
- timeout
- output schema/bounds
- precondition policy
- verification policy
- rollback policy where applicable

The existing parameterless fixed-action API is supported for compatibility. Control Plane v2 may add typed parameters only when the server implements strict validators and converts them into fixed internal operations.

## Authorization

Capabilities are granted individually. Suggested scope families:

- `edge1.status.read`
- `edge1.files.read`
- `edge1.files.stage`
- `edge1.files.apply`
- `edge1.repository.read`
- `edge1.repository.branch.write`
- `edge1.repository.deploy`
- `edge1.archive.read`
- `edge1.archive.write`
- `edge1.service.read`
- `edge1.service.control.safe`
- `edge1.service.control.privileged`
- `edge1.security.validate`
- `edge1.security.maintain`

An identity with `edge1.files.stage` is not automatically allowed to apply. An identity with repository branch-write access is not automatically allowed to deploy or fast-forward production.

## Mutation gates

A mutating request is accepted only if all applicable gates pass:

1. authenticated service/operator identity
2. required capability scope
3. capability enabled in the active manifest
4. broker mutation class enabled
5. valid input schema
6. target allowlist match
7. exact precondition match
8. valid idempotency key
9. approval/authorization state when required
10. backup or rollback material prepared when applicable
11. post-apply verification succeeds

Failure at any gate is fail-closed and audited.

## Repository writes

Repository write support is split deliberately:

- read status/head/diff/history
- fetch/prune
- create/update a dedicated agent branch
- validate/test branch
- open/update pull request
- reviewed merge/deploy

Direct mutation of `main` is not the default Big Bird write path. Production fast-forward/deploy remains a separate privileged capability.

## Filesystem writes

Named roots replace arbitrary paths. Example initial roots:

- `edge1-management-interface`
- `wwcx-deployment-staging`
- future `wwcx-archive-config`

Each root has an independent allowed operation set and excluded subpaths. Sensitive paths remain unavailable unless a purpose-built capability is added.

## Database/application writes

Do not expose SQL as a generic capability. Write through application-specific APIs/adapters with typed records, optimistic concurrency/version checks, and audit metadata.

Examples:

- Airtable/registry record adapters
- Paperless-ngx document metadata adapter
- Omeka S resource adapter
- ArchiveBox capture request adapter
- Zotero item/collection adapter

## Digital Archive integration

The WW.CX Digital Archive (#496) consumes Control Plane v2 capabilities:

- Open Library / Internet Archive: external discovery reads
- Zotero: research metadata read/write through API adapter
- Paperless-ngx: document metadata/index/workflow adapter
- ArchiveBox: capture and preservation adapter
- Omeka S: curated collection/resource adapter
- existing Drive/Dropbox/Library records remain authoritative for source documents unless explicitly migrated

## Migration

1. Freeze legacy connector feature development.
2. Add versioned capability manifest and schema.
3. Implement read-only compatibility against current Operations API.
4. Attach existing staged filesystem connector.
5. Add repository branch-write workflow.
6. Add archive adapters.
7. Add typed broker actions where fixed parameterless actions are insufficient.
8. Acceptance-test each mutation class in staging/fixtures.
9. Enable low-risk production write capabilities individually.
10. Disable legacy connector timers/services only after parity, rollback, and audit acceptance.

## Production rule

Do not solve this migration by globally setting `EDGE1_OPS_MUTATIONS_ENABLED=true` and enabling all disabled tools. The control plane must make mutation authorization granular, testable, reversible, and attributable.