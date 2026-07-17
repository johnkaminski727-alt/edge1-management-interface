# AI Filesystem Connector Phase 4 Register

Date: 2026-07-17

Status: ready to apply after Phase 3.

## Approved Scope

- Add operator-controlled apply for approved staged proposals only.
- Keep writes confined to the Edge1 management interface repository.
- Use configured allowlisted project paths.
- Hard-exclude secrets, credentials, environment files, SSH keys, service files,
  git internals, and paths outside the repository.
- Require explicit flags for executable script-style changes.
- Add pre-apply snapshots.
- Add post-apply verification.
- Add apply audit logging.
- Add rollback metadata.

## Explicitly Out of Scope

- Automatic approval.
- AI-initiated apply.
- Root-owned apply service.
- Rollback execution.

## Operator Acceptance

Run:

```bash
cd /opt/edge1-management-interface
python3 tests/validate_ai_filesystem_connector_phase4.py
```

Then confirm:

- Apply is refused before approval.
- Approved staged proposals can be applied by an operator.
- Snapshot metadata is written before apply.
- Verification metadata is written after apply.
- Rollback metadata is written but rollback is not executed.
- Secret-looking paths are rejected.
