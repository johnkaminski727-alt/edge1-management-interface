# Tool/API Contract: AI Filesystem Write Connector

Date: 2026-07-16
Status: proposed

## Purpose

This contract defines the bounded tool surface for AI-assisted filesystem
changes on Edge1.

## Tool Surface

| Tool | Mutates State | Purpose |
| --- | ---: | --- |
| `fs.stage` | yes | Stage a proposed file write. |
| `fs.inspect` | no | Read stage metadata. |
| `fs.diff` | no | Show running-to-candidate diff. |
| `fs.status` | no | Read stage/apply state. |
| `fs.request_apply` | yes | Request apply after approval exists. |
| `fs.audit.read` | no | Read connector audit events. |

Approval creation is intentionally not an AI tool. Approval must be created by
an operator-side command or UI action outside the model-controlled path.

## `fs.stage`

Input:

```json
{
  "target_path": "/opt/edge1-management-interface/docs/example.md",
  "content_sha256": "hex-encoded-sha256",
  "content": "text or file reference",
  "actor": "codex",
  "reason": "Document connector behavior"
}
```

Required validation:

- Target path is absolute.
- Target path normalizes without `..`.
- Target path is within an allowed root.
- Target file extension is allowed.
- Target does not contain forbidden path fragments.
- Content size is below the policy limit.
- Content hash matches supplied hash.
- Content scan finds no obvious secrets.

Output:

```json
{
  "stage_id": "opaque-stage-id",
  "status": "staged",
  "target_path": "/opt/edge1-management-interface/docs/example.md",
  "current_sha256": "hex-encoded-sha256-or-null",
  "proposed_sha256": "hex-encoded-sha256",
  "approval_required": true,
  "expires_at": "timestamp"
}
```

## `fs.inspect`

Input:

```json
{
  "stage_id": "opaque-stage-id"
}
```

Output includes:

- Stage id.
- Actor.
- Target path.
- Allowlist root.
- Current file existence.
- Current and proposed hashes.
- Size.
- Approval state.
- Expiry.
- Validation results.

## `fs.diff`

Input:

```json
{
  "stage_id": "opaque-stage-id",
  "format": "unified"
}
```

Output:

- Unified diff for text files.
- Structured warning when a diff cannot be safely rendered.

## `fs.request_apply`

Input:

```json
{
  "stage_id": "opaque-stage-id"
}
```

Required behavior:

- Refuse if approval does not exist.
- Refuse if stage expired.
- Refuse if staged content hash changed.
- Refuse if policy changed and target is no longer allowed.
- Queue or trigger root-owned apply processor.

## `fs.status`

Output states:

```text
staged
approved
apply_requested
applying
applied
failed
expired
rolled_back
```

## Implementation Notes

The MCP-facing tool may request apply, but the write itself should be performed
by a root-owned local processor. The MCP surface should never expose arbitrary
shell execution or unrestricted path writes.
