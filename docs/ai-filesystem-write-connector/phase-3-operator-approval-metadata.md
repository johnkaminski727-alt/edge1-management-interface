# AI Filesystem Connector Phase 3: Operator Approval Metadata

Phase 3 adds operator approval and rejection records for staged proposals.

It still does not add production filesystem apply, a root apply service,
automatic approval, or rollback execution.

## Boundary

Allowed in this phase:

- Mark a validated staged proposal as approved.
- Mark a staged proposal as rejected.
- Store `approval.json` alongside the staged proposal.
- Update `approval_status` in `manifest.json`.
- Audit approval, rejection, and status inspection events.

Not allowed in this phase:

- Applying changes to the target repository or production filesystem.
- Running a root-owned apply service.
- Automatically approving AI-generated proposals.
- Executing rollback.

## Commands

```bash
bin/bigbird-fsctl status <stage-id>
bin/bigbird-fsctl approve <stage-id> --by "John K." --note "Reviewed diff and validation."
bin/bigbird-fsctl reject <stage-id> --by "John K." --reason "Needs revision."
```

Approval is metadata only. It records operator intent for a later phase; it
does not write staged files into the repository.

## Acceptance Check

```bash
cd /opt/edge1-management-interface
python3 tests/validate_ai_filesystem_connector_phase3.py
```

Expected result:

```text
AI filesystem connector Phase 3 validation passed.
```
