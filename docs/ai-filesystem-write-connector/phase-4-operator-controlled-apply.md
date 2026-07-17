# AI Filesystem Connector Phase 4: Operator-Controlled Apply

Phase 4 adds operator-controlled apply for approved staged proposals inside the
Edge1 management interface repository.

It does not add automatic approval, AI-initiated apply, a root-owned apply
service, or rollback execution.

## Boundary

Allowed in this phase:

- Apply approved staged proposals only.
- Confine applied paths to the Edge1 management interface repository.
- Use configured allowlisted project paths.
- Hard-block secrets, credentials, environment files, SSH keys, git internals,
  service files, and anything outside the repository.
- Require explicit `allow_executable` on script-style changes.
- Write pre-apply snapshots.
- Verify applied file hashes after write.
- Write apply metadata and rollback metadata.
- Audit apply events.

Not allowed in this phase:

- Applying proposals that are not approved.
- Automatic approval.
- AI-initiated apply.
- Root-owned apply service.
- Rollback execution.

## Default Allowlist

```text
docs/
registers/
tests/
tools/handoff/
tools/ai_filesystem_connector/
server/
src/web/
bin/
config/examples/
```

## Hard Deny Rules

The connector rejects paths matching secret, credential, token, password, key,
certificate, environment, git-internal, service, or timer patterns. It also
rejects absolute paths, parent traversal, symlink targets, and symlink parents.

## Commands

```bash
bin/bigbird-fsctl policy
bin/bigbird-fsctl apply <stage-id> --by "John K."
bin/bigbird-fsctl status <stage-id>
```

The apply command re-validates the staged proposal immediately before writing.
If validation fails, approval is reset to `pending_review`.

## Policy Config

An operator may provide a JSON policy file with:

```json
{
  "allowed_prefixes": ["docs/", "registers/", "src/web/"],
  "deny_globs": ["*.env", "*.key", "*secret*", "*token*", ".git/*"]
}
```

Use it with:

```bash
bin/bigbird-fsctl --policy-config /path/to/policy.json policy
```

or:

```bash
export EDGE1_AI_FS_POLICY_CONFIG=/path/to/policy.json
```

## Acceptance Check

```bash
cd /opt/edge1-management-interface
python3 tests/validate_ai_filesystem_connector_phase4.py
```

Expected result:

```text
AI filesystem connector Phase 4 validation passed.
```
