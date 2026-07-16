# ADR-EDGE1-002: AI-Assisted Filesystem Write Connector

Date: 2026-07-16
Status: proposed
Decision owner: John
Implementation manager: Codex / Gus

## Context

Edge1 is becoming the authoritative private environment for Project Big Bird
operations, private knowledge, management interface work, approvals, audit
history, and future operator workflows.

The private model and Codex can help produce useful code, documentation, and
configuration proposals. However, unrestricted model write access to Edge1 would
create unacceptable operational and security risk.

Existing Edge1 direction already favors candidate/running state, validation,
human-readable diffs, checkpointed apply jobs, verification, rollback, and audit
history. The filesystem connector should follow that same discipline.

## Decision

Build a bounded AI-assisted filesystem write connector that accepts proposed
file changes but does not permit direct live writes by the model.

The connector must implement this lifecycle:

1. Stage proposed content and target path.
2. Validate policy, path, extension, size, content hash, and forbidden path
   patterns.
3. Generate inspectable metadata and diffs.
4. Require a root/operator approval record.
5. Apply with a root-owned processor.
6. Verify the applied file hash.
7. Record audit events.
8. Preserve rollback material.

## Non-Decision

This ADR does not approve unrestricted filesystem access, direct shell access,
automatic privileged command execution, direct edits to live firewall/DNS/VPN
configuration, or model-created approvals.

## Initial Allowlist

Initial writes may target only:

```text
/opt/edge1-management-interface
```

Initial file types should be limited to text-oriented project files:

```text
.css .html .js .json .md .py .ts .tsx .txt .yaml .yml
```

## Required Deny Rules

The connector must reject targets containing sensitive locations or names,
including at minimum:

```text
/.ssh/
/.gnupg/
/credentials/
/private_keys/
/secrets/
/shadow
/passwd
```

## Consequences

Positive consequences:

- AI can help advance Edge1 implementation without raw server control.
- Operators retain approval authority.
- Every proposed and applied change is inspectable and auditable.
- Rollback is part of the normal path.

Costs:

- More implementation work than raw write access.
- More operator ceremony for early changes.
- The allowlist must be maintained carefully as the system matures.

## Acceptance

This ADR is accepted only when the implementation passes the acceptance
checklist in `acceptance-checklist.md`.
