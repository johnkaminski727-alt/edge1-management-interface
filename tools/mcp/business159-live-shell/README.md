# Business159 Live Shell / Bounded Operator

This MCP server gives ChatGPT a bounded account-level operator for the WW.CX Business159 shared-host account. It intentionally does **not** model Business159 as a root-managed Linux host.

## Trust boundary

Defaults are discovery leads and remain environment-overridable:

- SSH alias: `business159`
- expected hostname: `business159.web-hosting.com`
- expected principal: `wwcxjywl`
- application checkout: `/home/wwcxjywl/apps/ww-cx-website`
- public root: `/home/wwcxjywl/public_html`
- shared deploy state: `/home/wwcxjywl/shared/ww-cx-website`
- received Edge1 operations snapshot: `/home/wwcxjywl/wwcx-store-private/operations-center/latest.json`

Every SSH-backed call runs with `BatchMode=yes`, strict host-key checking, a bounded timeout/output budget, and a remote hostname/principal guard before the requested command.

No password, token, key, cookie, session value, `.env` content, or private-key content should be returned. Output is capped and common secret patterns are redacted.

## Read-only bounded tools

- `business159.identity`
- `business159.health`
- `business159.snapshot`
- `business159.inventory`
- `business159.resources`
- `business159.php_status`
- `business159.web_status`
- `business159.domain_state`
- `business159.tls_status`
- `business159.cron_state`
- `business159.git_state`
- `business159.mail_state`
- `business159.deployment_status`
- `business159.edge1_bridge_status`
- `business159.config_digest`
- `business159.logs_summary`

`business159_connection_test` and `business159_inspect` provide the guarded shell layer for connectivity and narrow investigation without exposing arbitrary commands.

## Deployment

`business159_deploy` wraps the existing `ww-cx-website/scripts/deploy-business159.sh` mechanism rather than replacing it.

- Dry-run is the default and is available without enabling mutation.
- Apply is disabled unless `BUSINESS159_ALLOW_DEPLOY=1`.
- Apply requires an exact expected 40-character source commit.
- The dedicated deploy checkout must be clean before the existing deployer is invoked.
- A successful apply must also pass a post-deploy HTTPS request.

The deployer remains responsible for its existing source validation, document-root metadata invariants, backup, release metadata and release retention.

## Staged filesystem control

Filesystem mutation is disabled unless `BUSINESS159_ALLOW_FILESYSTEM=1`.

The controller accepts one small UTF-8 candidate at a time and only a validated relative path below the configured `public_html` root. It rejects parent traversal, absolute paths, secret-looking content, secret/config/database/backup filenames, and candidates above the configured size limit.

Lifecycle:

`stage -> status/diff -> approve -> apply -> verify -> rollback -> audit`

Stage data lives below `/home/wwcxjywl/shared/ww-cx-operator/stages/<stage-id>` by default. Apply requires an approval marker, preserves an existing target as a stage-local backup, uses a same-directory temporary file plus rename for file-level atomic replacement, verifies SHA-256 after activation, and preserves the target mode when replacing an existing file. Rollback restores that backup, or removes only a file that the same stage created.

This is deliberately **not** an arbitrary-path write API.

## Raw shell

`business159_exec` exists only as an attended escape hatch and is disabled unless `BUSINESS159_ENABLE_RAW_SHELL=1`. Normal inspection, troubleshooting, deploy, and staged file operations must use narrower tools.

## Installation

Install dependencies with the repository's normal Node/MCP packaging process, configure a reviewed SSH alias/known-host entry for Business159, and expose this package as the `business159-live-shell` MCP dependency. Do not put SSH keys or credentials in this repository or Skill packages.
