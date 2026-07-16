# Threat Model: AI Filesystem Write Connector

Date: 2026-07-16
Status: proposed

## Assets

- Edge1 operating system integrity.
- `/opt/edge1-management-interface` repository integrity.
- Private knowledge library integrity.
- Firewall, DNS, VPN, and routing configuration.
- Secrets, keys, credentials, and identity material.
- Audit history and approval records.

## Trust Boundaries

| Boundary | Rule |
| --- | --- |
| AI model to connector | Treat all requests as untrusted proposals. |
| Connector to staging | Staging is allowed only after validation. |
| Staging to live filesystem | Requires operator approval and root apply processor. |
| Apply processor to audit | Audit must be written for stage, approval, apply, failure, rollback. |
| Public ChatGPT to Edge1 | No unrestricted inbound server access. |

## Primary Risks And Mitigations

| Risk | Mitigation |
| --- | --- |
| Path traversal writes outside allowed roots | Normalize paths and reject `..`; map virtual paths under controlled roots. |
| Symlink escape | Resolve target parents, reject unsafe symlinks, write through safe temporary files. |
| Secret overwrite or exfiltration | Deny sensitive paths, scan content, never return secret file contents through diffs. |
| Model approves its own change | Keep approval creation outside the model tool surface. |
| Malicious content in staged file | Require reviewable diff, content scanning, and path-specific tests. |
| Race between review and apply | Verify staged hash and current policy immediately before apply. |
| Audit omission | Treat audit write failure as apply failure. |
| Destructive broad change | Limit initial scope to single-file or small batch changes. |
| Rollback unavailable | Create backup/checkpoint before apply and verify backup exists. |
| Confusing shell instructions | Label all commands with target host and avoid mixing outputs with commands. |

## Explicitly Forbidden For Initial Release

- Raw shell access.
- Writes to `/etc`, `/root`, `/home/*/.ssh`, package manager state, or service
  unit directories.
- Direct firewall, DNS, VPN, route, or identity mutation.
- Model-created approvals.
- Automatic apply without human/operator authorization.
- Credential retrieval.

## Initial Safe Use Cases

- Documentation updates under `/opt/edge1-management-interface/docs`.
- README and changelog updates.
- Non-secret management interface source changes after tests exist.
- Private library reference stubs and project manifests.

## Open Questions

- Exact root-owned service name.
- Whether approvals should live in SQLite, signed JSON records, or both.
- Maximum initial batch size.
- Required tests before management interface source changes are allowed.
