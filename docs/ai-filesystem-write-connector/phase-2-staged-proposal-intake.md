# AI Filesystem Connector Phase 2: Staged Proposal Intake

Phase 2 adds implementation for staged proposal intake, inspection, validation,
and audit logging only.

It does not add production filesystem apply, a root apply service, automatic
approval, or rollback execution.

## Boundary

Allowed in this phase:

- Stage proposed text changes from a JSON proposal.
- Validate proposal paths and content against a conservative policy.
- Write proposed files into a staging directory.
- Generate a unified diff for operator inspection.
- Show, list, diff, and re-validate staged proposals.
- Append JSONL audit events for each operator action.

Not allowed in this phase:

- Applying changes to the target repository or production filesystem.
- Approving staged proposals.
- Running a root-owned apply service.
- Executing rollback.
- Granting the model arbitrary filesystem write access.

## CLI

The repository-local command is:

```bash
bin/bigbird-fsctl --help
```

Stage a proposal:

```bash
bin/bigbird-fsctl \
  --repo /opt/edge1-management-interface \
  stage --proposal /path/to/proposal.json
```

Inspect it:

```bash
bin/bigbird-fsctl list
bin/bigbird-fsctl show <stage-id>
bin/bigbird-fsctl diff <stage-id>
bin/bigbird-fsctl validate <stage-id>
```

The default production staging paths are:

```text
/var/lib/edge1-ai-fs-connector/staged
/var/log/edge1-ai-fs-connector/audit.jsonl
```

For non-root smoke tests, override them:

```bash
export EDGE1_AI_FS_STAGE_ROOT=/tmp/edge1-ai-fs-staged
export EDGE1_AI_FS_AUDIT_LOG=/tmp/edge1-ai-fs-audit.jsonl
```

## Proposal Format

```json
{
  "description": "Add an operator note",
  "actor": "ai-assistant",
  "changes": [
    {
      "path": "docs/ai-filesystem-write-connector/example.md",
      "mode": "replace",
      "content": "# Example\n\nStaged text only.\n"
    }
  ]
}
```

By default, Phase 2 accepts only paths under:

```text
docs/
registers/
```

The proposal may narrow or adjust this for testing with:

```json
{
  "policy": {
    "allowed_prefixes": ["docs/", "registers/"]
  }
}
```

## Acceptance Check

```bash
cd /opt/edge1-management-interface
python3 tests/validate_ai_filesystem_connector_phase2.py
```

Expected result:

```text
AI filesystem connector Phase 2 validation passed.
```
