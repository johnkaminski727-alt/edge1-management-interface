# Edge1 Live Shell MCP Connector

A guarded SSH-backed MCP sidecar for **attended escalation and fallback work** on Edge1. It is not the normal production ChatGPT Edge1 Operator.

The canonical production Operator is the hardened `edge1-operator-mcp.service` described in `docs/edge1-operator/`. Its reviewed named tool contract is defined by `server/edge1_operator_mcp_protocol.py` and deliberately excludes generic shell execution. Prefer that Operator and the Secure MCP Tunnel transport for ordinary ChatGPT access.

## Security model

- No credentials, private keys, tokens, hostnames, or private addresses are stored here.
- SSH uses `BatchMode=yes` and strict host-key checking.
- Read-only inspection is enabled by default.
- Service restart, Cookie Monster mutation actions, Edge1 release mutations and raw shell are disabled by default.
- Repositories and restartable services are allowlisted through environment variables.
- Cookie Monster accepts only a fixed action enum; it accepts no path, URL, command, credential or arbitrary dataset.
- Cookie Monster source sync and activation are pinned to one explicitly supplied reviewed Git commit, never an open-ended `origin/main` deployment.
- Edge1 release reconciliation accepts only `status`, `reconcile`, or `rollback_last`; promotion identity is pinned to one exact environment-supplied commit and never comes from caller text.
- Output is capped, timed out, and passed through basic secret redaction before being returned.
- This sidecar must not be merged into, substituted for, or advertised as the canonical production `edge1-operator-mcp` tool surface.

## Appropriate use

Use this component only when an attended, explicitly authorized task cannot be completed through the canonical named Operator tools or another narrower approved interface. Examples include bounded repository/service diagnosis from an already-authorized SSH connector host, the fixed Cookie Monster Alpha staging activation transaction, durable Edge1 control-plane release reconciliation, or a narrowly scoped service restart when its environment and sudo allowlist have been deliberately enabled.

Do not attach this sidecar to the ordinary ChatGPT Edge1 custom app merely to gain generic command execution. `edge1_exec` being present here does not make generic shell part of the accepted production Operator contract.

## Requirements

- Node.js 20+
- OpenSSH client
- A working SSH alias `edge1` configured outside the repository
- A least-privilege remote account
- For service restart, only exact `sudo -n systemctl restart <allowlisted-service>` privileges for approved services
- For Cookie Monster activation, a non-interactive sudo policy sufficient to invoke only the reviewed activation script, or an equivalent already-approved restricted elevation path
- For release reconciliation, a non-interactive sudo policy sufficient to run the reviewed release-controller installer/controller and the controller's fixed service transaction; no generic root shell is required

## Install and test

```sh
cd tools/mcp/edge1-live-shell
npm install
npm run check
npx @modelcontextprotocol/inspector node src/index.js
```

Run `edge1_connection_test` first. It must return the expected Edge1 hostname and authenticated principal before any other sidecar operation.

## Environment

```text
EDGE1_SSH_ALIAS=edge1
EDGE1_ALLOW_RESTARTS=0
EDGE1_ALLOW_COOKIE_MONSTER=0
EDGE1_COOKIE_MONSTER_TARGET_SHA=<reviewed-40-character-git-commit>
EDGE1_ALLOW_RELEASES=0
EDGE1_RELEASE_TARGET_SHA=<reviewed-40-character-git-commit>
EDGE1_ENABLE_RAW_SHELL=0
EDGE1_ALLOWED_SERVICES=bigbird-ai-gateway
EDGE1_REPOSITORIES=edge1-interface=/opt/edge1-management-interface;bigbird-gateway=/opt/bigbird-ai-gateway
EDGE1_TIMEOUT_MS=30000
EDGE1_MAX_OUTPUT_BYTES=24000
```

`EDGE1_COOKIE_MONSTER_TARGET_SHA` and `EDGE1_RELEASE_TARGET_SHA` are exact reviewed 40-character lowercase Git commits. They are deployment identities, not credentials. The sidecar refuses the corresponding commit-pinned mutation when a required target is missing or malformed.

Keep private addresses and key paths in SSH configuration, never in these variables or the repository.

## Sidecar MCP tools

- `edge1_connection_test`
- `edge1_inspect`
- `edge1_restart_service` (policy-gated; disabled by default)
- `edge1_cookie_monster` (fixed Alpha lifecycle; mutations policy-gated)
- `edge1_release` (durable source/runtime reconciliation; mutations policy-gated)
- `edge1_exec` (attended/policy-gated; disabled by default)

### Cookie Monster actions

`edge1_cookie_monster` accepts exactly one `action` value and no other execution authority:

- `preflight` — run the activation script's read-only preflight through the approved elevation path;
- `sync_sources` — require the allowlisted Edge1 repository to be clean on `main`, fetch `origin`, verify the pinned target is a commit reachable from `origin/main`, and fast-forward only to that exact target;
- `activate` — first require the repository HEAD to equal the pinned target, then run the bounded root-only Alpha staging transaction from `deploy/cookie_monster_edge1_activate.py --apply`;
- `rollback_last` — invoke the activation transaction's recorded rollback pointer.

`sync_sources`, `activate`, and `rollback_last` all require:

```text
EDGE1_ALLOW_COOKIE_MONSTER=1
```

`sync_sources` and `activate` additionally require a valid `EDGE1_COOKIE_MONSTER_TARGET_SHA`. Source sync refuses a dirty tree, refuses a non-`main` branch, fetches `origin`, proves the exact target is an ancestor of `origin/main`, and uses `git merge --ff-only <target>`. It does not deploy whatever `origin/main` happens to be at execution time and does not reset, clean, stash, rebase or force-push anything.

The activation script itself restricts mutation to the canonical `/opt/edge1-management-interface` repository, fixed `alpha-staging` dataset and private runtime paths. Its minimized operator view is staged under `/var/lib/cookie-monster-alpha/operator-view`; it does not write the Apache-served `/var/www/edge1-status` boundary.

### Edge1 release actions

`edge1_release` accepts exactly:

- `status` — read/publish the persistent release-controller status; if the controller is not installed yet, report that condition without mutating the host;
- `reconcile` — bootstrap the durable controller from a temporary detached worktree at the exact pinned target, create/validate the dedicated source checkout, prepare the exact runtime release, atomically promote it, restart only the fixed managed control-plane services, run postflight and publish status;
- `rollback_last` — return to the exact controller-recorded previous release, with no caller-supplied path or commit.

`reconcile` and `rollback_last` require:

```text
EDGE1_ALLOW_RELEASES=1
```

`reconcile` also requires a valid `EDGE1_RELEASE_TARGET_SHA`. The target is fetched and verified as reachable from `origin/main`, but the command never deploys a moving `origin/main` tip. First bootstrap uses a temporary detached worktree so a detached or stale legacy runtime checkout does not have to be converted into the permanent source tree before the controller can install itself.

After installation the permanent model is:

```text
/opt/edge1-management-source        mutable clean main source
/opt/edge1-runtime/releases/<sha>   exact detached releases
/opt/edge1-runtime/current          active pointer
/opt/edge1-runtime/previous         exact rollback pointer
```

The release controller manages only `edge1-operations-api.service` and `edge1-operator-mcp.service` initially. It verifies Operations API root stability, mutation denial, service health, and loopback-only listeners and automatically attempts to restore the former release if promotion postflight fails.

Keep `EDGE1_ENABLE_RAW_SHELL=0` while using either named mutation surface. The point is to complete attended operational work without widening the session to arbitrary command execution.

## ChatGPT architecture

For the permanent ChatGPT Operator, follow `docs/edge1-operator/14-secure-mcp-tunnel.md`: ChatGPT custom MCP app -> Secure MCP Tunnel -> loopback `edge1-operator-mcp`. Use `prompts/edge1-authenticated-operator.md` as the operator prompt.

Treat this SSH sidecar as a separate escalation path and keep it detached unless an attended task specifically needs it.
