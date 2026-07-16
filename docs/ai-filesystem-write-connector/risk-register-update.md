# Risk Register Update: AI Filesystem Write Connector

Date: 2026-07-16
Status: proposed

## New Risk: AI-Assisted Filesystem Writes

Risk: AI-assisted tooling could write incorrect, unsafe, overly broad, or
unauthorized content to the Edge1 filesystem.

Impact:

- Service disruption.
- Configuration drift.
- Secret exposure.
- Loss of operator confidence.
- Difficult recovery if rollback is incomplete.

Mitigations:

- Initial writes limited to `/opt/edge1-management-interface`.
- No raw shell or unrestricted write tool.
- Stage, inspect, diff, approve, apply, verify, audit, rollback lifecycle.
- Operator approval cannot be created by the AI tool path.
- Root-owned apply processor performs live writes.
- Required path normalization and denylist checks.
- Required hash verification before and after apply.
- Required audit events.
- Required backup/checkpoint before apply.

Residual risk:

- Operator may approve a bad diff.
- Allowlist may be expanded too quickly.
- Tests may be insufficient for future source-code changes.

Required controls before production:

1. Acceptance checklist complete.
2. Operator runbook installed.
3. Audit event schema implemented.
4. Rollback tested.
5. First release limited to documentation-only writes.
