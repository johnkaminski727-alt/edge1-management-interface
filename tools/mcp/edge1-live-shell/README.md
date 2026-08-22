# Edge1 Live Shell MCP Connector

A guarded SSH-backed MCP sidecar for **attended escalation and fallback work** on Edge1. It is not the normal production ChatGPT Edge1 Operator.

The canonical production Operator is the hardened `edge1-operator-mcp.service` described in `docs/edge1-operator/`. Its reviewed named tool contract is defined by `server/edge1_operator_mcp_protocol.py` and deliberately excludes generic shell execution. Prefer that Operator and the Secure MCP Tunnel transport for ordinary ChatGPT access.

## Security model

- No credentials, private keys, tokens, hostnames, or private addresses are stored here.
- SSH uses `BatchMode=yes` and strict host-key checking.
- Read-only inspection is enabled by default.
- Service restart, Cookie Monster mutation actions and raw shell are disabled by default.
- Repositories and restartable services are allowlisted through environment variables.
- Cookie Monster accepts only a fixed action enum; it accepts no path, URL, command, credential or arbitrary dataset.
- Output is capped, timed out, and passed through basic secret redaction before being returned.
- This sidecar must not be merged into, substituted for, or advertised as the canonical production `edge1-operator-mcp` tool surface.

## Appropriate use

Use this component only when an attended, explicitly authorized task cannot be completed through the canonical named Operator tools or another narrower approved interface. Examples include bounded repository/service diagnosis from an already-authorized SSH connector host, the fixed Cookie Monster Alpha staging activation transaction, or a narrowly scoped service restart when its environment and sudo allowlist have been deliberately enabled.

Do not attach this sidecar to the ordinary ChatGPT Edge1 custom app merely to gain generic command execution. `edge1_exec` being present here does not make generic shell part of the accepted production Operator contract.

## Requirements

- Node.js 20+
- OpenSSH client
- A working SSH alias `edge1` configured outside the repository
- A least-privilege remote account
- For service restart, only exact `sudo -n systemctl restart <allowlisted-service>` privileges for approved services
- For Cookie Monster activation, a non-interactive sudo policy sufficient to invoke only the reviewed activation script, or an equivalent already-approved restricted elevation path

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
EDGE1_ENABLE_RAW_SHELL=0
EDGE1_ALLOWED_SERVICES=bigbird-ai-gateway
EDGE1_REPOSITORIES=edge1-interface=/opt/edge1-management-interface;bigbird-gateway=/opt/bigbird-ai-gateway
EDGE1_TIMEOUT_MS=30000
EDGE1_MAX_OUTPUT_BYTES=24000
```

Keep private addresses and key paths in SSH configuration, never in these variables or the repository.

## Sidecar MCP tools

- `edge1_connection_test`
- `edge1_inspect`
- `edge1_restart_service` (policy-gated; disabled by default)
- `edge1_cookie_monster` (fixed Alpha lifecycle; mutations policy-gated)
- `edge1_exec` (attended/policy-gated; disabled by default)

### Cookie Monster actions

`edge1_cookie_monster` accepts exactly one `action` value and no other execution authority:

- `preflight` — run the activation script's read-only preflight through the approved elevation path;
- `sync_sources` — require the allowlisted Edge1 repository to be clean on `main`, fetch `origin`, and perform only a fast-forward merge of `origin/main`;
- `activate` — run the bounded root-only Alpha staging transaction from `deploy/cookie_monster_edge1_activate.py --apply`;
- `rollback_last` — invoke the activation transaction's recorded rollback pointer.

`sync_sources`, `activate`, and `rollback_last` all require:

```text
EDGE1_ALLOW_COOKIE_MONSTER=1
```

The source-sync action refuses a dirty tree, refuses a non-`main` branch, and uses `git merge --ff-only`; it does not reset, clean, stash, rebase or force-push anything. The activation script itself restricts mutation to the canonical `/opt/edge1-management-interface` repository, fixed `alpha-staging` dataset, local runtime paths and private cockpit.

Keep `EDGE1_ENABLE_RAW_SHELL=0` while using the named Cookie Monster action. The purpose of this surface is to complete the attended rollout without widening the session to arbitrary command execution.

## ChatGPT architecture

For the permanent ChatGPT Operator, follow `docs/edge1-operator/14-secure-mcp-tunnel.md`: ChatGPT custom MCP app -> Secure MCP Tunnel -> loopback `edge1-operator-mcp`. Use `prompts/edge1-authenticated-operator.md` as the operator prompt.

Treat this SSH sidecar as a separate escalation path and keep it detached unless an attended task specifically needs it.
