# Acceptance Checklist: AI Filesystem Write Connector

Date: 2026-07-16
Status: proposed

## Documentation Acceptance

- [ ] ADR is committed under `/opt/edge1-management-interface/docs`.
- [ ] Operator runbook is committed.
- [ ] API/tool contract is committed.
- [ ] Threat model is committed.
- [ ] Audit event schema is committed.
- [ ] Rollback procedure is committed.
- [ ] Risk register update is committed or cross-referenced.
- [ ] Changelog entry is committed or merged into project changelog.
- [ ] Consolidated private-library import document is staged.
- [ ] Private-library import is approved by root/operator.
- [ ] Private-library search verifies the new documentation is retrievable.

## Implementation Acceptance

- [ ] Connector accepts staged content without live write.
- [ ] Connector rejects unapproved apply.
- [ ] Connector rejects targets outside allowed roots.
- [ ] Connector rejects forbidden path fragments.
- [ ] Connector rejects unsupported file extensions.
- [ ] Connector records current and proposed SHA-256 hashes.
- [ ] Connector renders a safe diff for text files.
- [ ] Operator approval is required outside the AI tool path.
- [ ] Root-owned apply processor performs live write.
- [ ] Apply creates backup or checkpoint.
- [ ] Apply verifies written SHA-256.
- [ ] Audit events are written for stage, approval, apply, failure, and rollback.
- [ ] Rollback is tested successfully.
- [ ] First production release is documentation-only.

## Stop-Ship Safety Gate

Release must stop if any of the following are true:

- Raw shell access is exposed to the model.
- The model can approve its own change.
- Connector can write to `/etc`, `/root`, credentials, keys, firewall, DNS,
  VPN, or service configuration in the first release.
- Apply succeeds when audit logging fails.
- Apply succeeds without backup/checkpoint.
- Path traversal or symlink escape is possible.
