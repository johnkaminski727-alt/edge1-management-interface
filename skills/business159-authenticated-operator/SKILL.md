---
name: business159-authenticated-operator
description: Execute authorized WW.CX operational work on the Business159 shared-host account through the bounded Business159 connector. Use for Business159 repair, deployment, PHP/web troubleshooting, repository handling, cron/application-log investigation, staged public-root changes, verification, rollback, and evidence capture while enforcing cPanel/shared-host constraints and least privilege.
---

# Business159 Authenticated Operator

Operate Business159 as an account-level shared host, not as Edge1.

Use this lifecycle:

`inspect -> preflight -> classify risk -> preserve state -> smallest change -> validate -> capture evidence -> roll back if needed`

## Preflight

Verify the Business159 host/principal with `business159_connection_test`, inspect relevant bounded state, and identify the exact application/repository/path/deployment target. Preserve unrelated work; never reset, clean, stash, or overwrite an unknown working tree merely to make deployment convenient.

## Preferred operations

- Read-only state: named `business159.*` tools or `business159_inspect`.
- Deployment: `business159_deploy`, using dry-run before apply and an exact expected source commit for apply.
- File change: `business159_fs_*` staged lifecycle.
- Raw shell: `business159_exec` only for an explicitly authorized gap that narrower tools cannot handle.

Understand PHP, document roots, redirects/`.htaccess`, Git, cron, account logs, deployment metadata, public/private boundaries, and the existing WW.CX deployment scripts.

Never claim systemd/root/firewall/kernel control. Never request or expose credentials. Stop before DNS, certificate issuance/replacement, authentication-policy changes, billing/legal actions, destructive deletion, shared-history rewrite, or production calling/messaging changes unless separately and explicitly authorized.

A command exit code alone is not completion. Verify repository/file state plus functional HTTP/PHP behavior where relevant, and preserve rollback evidence.
