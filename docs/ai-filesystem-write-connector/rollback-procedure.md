# Rollback Procedure: AI Filesystem Write Connector

Date: 2026-07-16
Status: proposed

## Purpose

Rollback must be available for every applied filesystem connector change.

## Preconditions

Before apply, the connector must record:

- Stage id.
- Target path.
- Current file existence.
- Current content hash.
- Proposed content hash.
- Backup path or deletion marker.
- Approval actor.
- Apply processor identity.

## Normal Rollback Workflow

1. Identify the stage id.
2. Inspect the audit record.
3. Confirm the target path.
4. Confirm the backup path or deletion marker.
5. Stage rollback as a new operation.
6. Review rollback diff.
7. Approve rollback as root/operator.
8. Apply rollback through the root-owned processor.
9. Verify restored hash.
10. Record rollback audit events.

## Example Future Commands

Please run this on Edge1:

```bash
sudo /usr/local/sbin/bigbird-fsctl status <stage_id>
sudo /usr/local/sbin/bigbird-fsctl rollback-plan <stage_id>
sudo /usr/local/sbin/bigbird-fsctl rollback-diff <stage_id>
sudo /usr/local/sbin/bigbird-fsctl approve-rollback --by John <stage_id>
sudo /usr/local/sbin/bigbird-fsctl rollback <stage_id>
```

## Git-Backed Targets

For git-backed targets such as `/opt/edge1-management-interface`, rollback may
also be possible through git. The connector rollback record should still exist
because it records the operational apply path.

Recommended verification:

```bash
cd /opt/edge1-management-interface
git status --short
git log --oneline -5
```

## Failure Handling

If rollback fails:

- Stop further applies for the same allowed root.
- Preserve all staged material.
- Preserve backup material.
- Record `fs.rollback_failed`.
- Escalate to manual operator recovery.
