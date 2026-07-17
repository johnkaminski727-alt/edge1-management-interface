# Edge1 AI Filesystem Write Connector Phase 1

Date: 2026-07-16
Status: installable candidate
Scope: documentation-only filesystem writes

## Purpose

Phase 1 installs a local operator CLI called `bigbird-fsctl`. It implements the
safe filesystem-write lifecycle documented in
`/opt/edge1-management-interface/docs/ai-filesystem-write-connector`, but limits
live writes to documentation paths only.

## Initial Production Scope

Allowed target root:

```text
/opt/edge1-management-interface/docs
```

Allowed file types:

```text
.json .md .txt .yaml .yml
```

Forbidden initial release behavior:

- No raw shell access for the model.
- No writes outside `/opt/edge1-management-interface/docs`.
- No writes to firewall, DNS, VPN, route, identity, credential, or service
  configuration.
- No automatic apply without approval.

## Installed Paths

| Path | Purpose |
| --- | --- |
| `/usr/local/sbin/bigbird-fsctl` | Operator CLI. |
| `/etc/bigbird-fsctl/policy.json` | Docs-only policy. |
| `/var/lib/bigbird-fsctl/staging` | Staged proposals. |
| `/var/lib/bigbird-fsctl/backups` | Rollback material. |
| `/var/log/bigbird-fsctl/audit.jsonl` | JSONL audit trail. |

## Lifecycle

```text
stage -> inspect -> diff -> approve -> apply -> status -> audit
```

Rollback is available for applied stages:

```text
rollback
```

## Example

Please run this on Edge1:

```bash
sudo bigbird-fsctl stage \
  --source /tmp/example.md \
  --target /opt/edge1-management-interface/docs/example.md \
  --actor John \
  --reason "Test documentation-only write"

sudo bigbird-fsctl inspect STAGE_ID
sudo bigbird-fsctl diff STAGE_ID
sudo bigbird-fsctl approve --by John STAGE_ID
sudo bigbird-fsctl apply STAGE_ID
sudo bigbird-fsctl status STAGE_ID
sudo bigbird-fsctl audit --limit 10
```

## Git Commit After Apply

For changes inside `/opt/edge1-management-interface`, commit normally after
reviewing the working tree:

```bash
cd /opt/edge1-management-interface
git status --short
git add docs
git commit -m "Apply filesystem connector documentation update"
```
