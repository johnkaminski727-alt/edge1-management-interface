# WW.CX Multi-Host Operator Architecture

## Purpose

WW.CX operates two deliberately different privilege domains:

- **Edge1** — private operations/control plane with machine/service/network capabilities governed by the existing bounded Edge1 Operator and guarded authenticated workflows.
- **Business159** — cPanel/shared-host public application plane with account-level SSH, PHP, webroots, Git, cron, application logs, deployment metadata, and HTTP/HTTPS capabilities only.
- **Cross-host layer** — Skill-level orchestration and release verification across both hosts without pretending they have identical privileges.

The operator architecture prefers live bounded tools over raw shell, and composition over duplicating policy logic.

## Edge1 contract

The ordinary Edge1 status surface remains the accepted 16 zero-argument `edge1.*` tools. Separate `agent.turn.status` and `agent.turn.handoff` tools belong to coordination state and are not part of ordinary host-status routing. The existing Edge1 filesystem controller remains restricted to its approved documentation path; this multi-host work does not broaden it.

## Business159 bounded operator

Source: `tools/mcp/business159-live-shell/`.

The connector exposes 16 ordinary read-only tools:

`business159.identity`, `health`, `snapshot`, `inventory`, `resources`, `php_status`, `web_status`, `domain_state`, `tls_status`, `cron_state`, `git_state`, `mail_state`, `deployment_status`, `edge1_bridge_status`, `config_digest`, and `logs_summary`.

Every SSH call uses batch authentication, strict host-key checking, bounded timeout/output, output redaction, and an expected-host/expected-principal check before the requested remote command.

Business159 does not expose systemd, root, firewall, kernel, or host-level network controls.

## Guarded Business159 operations

- `business159_connection_test` — verify account/host identity.
- `business159_inspect` — bounded read-only investigation.
- `business159_deploy` — safety wrapper around the existing `ww-cx-website/scripts/deploy-business159.sh` implementation; dry-run by default; apply requires the environment gate and exact expected commit.
- `business159_fs_*` — stage/status/diff/approve/apply/rollback lifecycle confined to validated relative paths under the configured `public_html` root.
- `business159_exec` — attended escape hatch, disabled by default.

Mutation gates are environment-controlled and default off. No credentials belong in connector configuration committed to Git.

## Business159 staged filesystem lifecycle

`stage -> status/diff -> approve -> backup -> file-level atomic apply -> SHA-256 verify -> audit -> rollback if required`

Candidates are size-bounded and rejected when the target path or content looks like credential, key, token, cookie/session, environment-secret, database, log, or backup material. Stage state and audit metadata live below the private shared operator root, not the webroot.

## Existing Business159 deployment

The canonical website deployment remains in `johnkaminski727-alt/ww-cx-website`. The operator wraps it rather than replacing it.

The hardened deploy branch requires a clean dedicated checkout, advances source by fast-forward only, validates before deployment, preserves the document-root ownership/group/mode invariants, uses exact synchronization, performs a functional HTTPS health check, and invokes the existing release rollback path when verification fails and a previous release is available.

## Edge1 -> Business159 Operations Center bridge

The Business159 application consumes the received Edge1 snapshot from `/home/wwcxjywl/wwcx-store-private/operations-center/latest.json` by default. The application already supports receiver-side SHA-256 sidecar verification and an HMAC mode without exposing the verification key.

Cross-host diagnosis follows:

`Edge1 producer -> sanitized state -> integrity artifact -> transfer -> Business159 private snapshot -> checksum/signature verification -> application consumer -> HTTP/UI`

The `business159.edge1_bridge_status` tool reports only file freshness/integrity metadata. The `wwcx-cross-host-operator` composes that with live Edge1 evidence when both connectors are available.

## Skills

Source-controlled Skill packages:

- `business159-operator-router`
- `business159-shell-operator`
- `business159-filesystem-operator`
- `business159-authenticated-operator`
- `business159-web-operator`
- `shared-host-security-auditor`
- `wwcx-cross-host-operator`
- `wwcx-release-operator`

Each package contains `SKILL.md` and `agents/openai.yaml`. Runtime machine state stays in tools; stable routing/safety policy stays in Skills.

## Testing

`.github/workflows/business159-operator.yml` validates connector syntax/imports, required tool names, parameterless ordinary read-only schemas, strict SSH controls, mutation feature gates, staged-filesystem safety controls, and required Skill package structure.

Live read-only acceptance still requires the actual connector to be installed/attached. Do not mark repository-level or CI validation as live-host validation.

## Security boundaries

Never expose credentials, signing keys, tokens, cookies, or secret configuration values. Never disable SSH host verification. Never broaden Business159 to arbitrary paths or Edge1-equivalent machine authority. DNS, firewall, certificates, authentication, irreversible deletion, shared Git history rewrites, billing/legal actions, and production calling/messaging remain separately gated.
