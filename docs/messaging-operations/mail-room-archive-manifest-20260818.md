# Mail Room archive manifest — 2026-08-18

## Scope and preservation boundary

Repository: `johnkaminski727-alt/edge1-management-interface`.

This manifest preserves the repository-side Mail Room checkpoint. Git commit and merge SHAs are the canonical content identity for repository artifacts; no destructive archival action or duplicate repository-tree hashing is performed. Source material remains in Git history.

Feature checkpoint before archive documentation: `50f5ef6273fa7ac2e7f0579e76578d9e1e08ad16`.

## Authoritative continuation records

- `.agent/mail-room-current-state-20260818.md` — verified capability/state and architecture index.
- `.agent/mail-room-validation-20260818.md` — exact CI run evidence and validation limitations.
- `.agent/mail-room-backlog-20260818.md` — privileged blockers, safe future work, and regression prohibitions.
- `.agent/mail-room-handoff-20260818.md` — resume point and next action.
- `docs/messaging-operations/mail-room-production-activation-checklist-20260818.md` — privileged activation gates.
- This manifest — archive scope and artifact index.

## Core implementation artifacts

Inbound / identity / routing:
- `server/inbound_mail_hub.py`
- `server/mail_identity_registry.py`
- `server/identity_aware_outbound_gateway.py`
- `config/messaging/inbound-mail-hub.json`
- `config/messaging/mail-identities.json`

Correspondence / delivery:
- `server/mail_threading.py`
- `server/outbound_mail_delivery_events.py`
- associated delivery-event CLI/tests/schemas/workflows under the repository messaging paths.

Outbound security:
- `server/outbound_mail_gateway.py`
- `server/mail_final_scan.py`
- `server/mail_secure_submission.py`
- `server/mail_auto_reply_policy.py`
- `config/messaging/outbound-mail-gateway.json`
- `config/messaging/outbound-mail-policy.json`
- auto-reply policy configuration added by PR #366.

Threat / quarantine:
- `config/messaging/mail-threat-policy.json`
- `server/mail_threat_decision.py`
- `server/mail_quarantine.py`

Domain consistency / provider observation:
- `server/mail_config_consistency.py`
- `tools/messaging/mail_domain_inventory.py`
- `config/messaging/mail-provider-inventory.json`
- `records/messaging/dns-inventories/` for historical read-only observations.

## Key merge lineage

- #362 `75539c9c97e29a25127aef21b58166bdaf3a97a9`
- #364 `43c00e4fd6792ee783ee4542226ad54149b23a34`
- #365 `00640677a2a0b9d010079394ff1f8a137c84db59`
- #366 `f57478fc7f9a7174ff9c6ccefcfda627b734fb53`
- #367 `e57cbb8a5533b4bf8d03daef7230ecd3570f0f99`
- #368 `a606f8f171da3de63b564512eb7c0aaba92710df`
- #369 `50f5ef6273fa7ac2e7f0579e76578d9e1e08ad16`

## Sensitive-data boundary

This archive checkpoint intentionally contains no credentials, secret values, private keys, raw malicious payloads, or message bodies. Operational configurations name environment-variable locations/purposes rather than credential values.

## Completion status

Repository reconciliation reached the current `main` history and all feature PRs created in this continuation were merged after successful GitHub Actions validation. Production-provider, scanner-runtime, DNS, mailbox, live-routing, live-transmission, and quarantine-release evidence is intentionally absent because those actions were outside the authorized boundary.

The archive is therefore complete for the repository-side checkpoint, not for production deployment or production verification.
