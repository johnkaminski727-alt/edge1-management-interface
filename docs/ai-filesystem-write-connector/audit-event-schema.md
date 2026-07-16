# Audit Event Schema: AI Filesystem Write Connector

Date: 2026-07-16
Status: proposed

## Purpose

Every connector action must create enough audit detail to reconstruct who
proposed a change, what was proposed, who approved it, what was applied, and how
rollback can be performed.

## Required Event Types

```text
fs.stage
fs.inspect
fs.diff
fs.approve
fs.request_apply
fs.apply_started
fs.apply_succeeded
fs.apply_failed
fs.rollback_started
fs.rollback_succeeded
fs.rollback_failed
fs.stage_expired
fs.stage_rejected
```

Read-only inspect and diff events may be sampled later if the volume becomes
high, but initial release should log them.

## Required JSON Fields

```json
{
  "event_id": "opaque-event-id",
  "event_type": "fs.apply_succeeded",
  "occurred_at": "2026-07-16T00:00:00Z",
  "server": "edge1",
  "actor": "root-apply-processor",
  "request_actor": "codex",
  "approval_actor": "John",
  "stage_id": "opaque-stage-id",
  "target_path": "/opt/edge1-management-interface/docs/example.md",
  "allowed_root": "management-interface",
  "current_sha256_before": "hex-or-null",
  "proposed_sha256": "hex",
  "written_sha256": "hex",
  "backup_path": "/var/lib/bigbird/fs-connector/backups/stage-id/previous",
  "result": "succeeded",
  "reason": "Document connector behavior",
  "error_code": null,
  "error_message": null,
  "correlation_id": "opaque-correlation-id"
}
```

## Privacy Rules

- Do not log full file contents in audit records.
- Do not log secrets.
- Do not log temporary signed URLs.
- Do not log private key material.
- Hashes, paths, actors, and stage ids are required.

## Integrity Rules

- Audit writes must happen before and after apply.
- Apply must fail if a required audit record cannot be written.
- Audit records should be append-only.
- Audit records should be included in future management interface audit views.
