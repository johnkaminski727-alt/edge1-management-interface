# Edge1 Live Shell MCP Connector

A guarded SSH-backed MCP sidecar for **attended escalation and fallback work** on Edge1. It is not the normal production ChatGPT Edge1 Operator.

The canonical production Operator is the hardened `edge1-operator-mcp.service` described in `docs/edge1-operator/`. Its reviewed named tool contract is defined by `server/edge1_operator_mcp_protocol.py` and deliberately excludes generic shell execution. Prefer that Operator and the Secure MCP Tunnel transport for ordinary ChatGPT access.

## Security model

- No credentials, private keys, tokens, hostnames, or private addresses are stored here.
- SSH uses `BatchMode=yes` and strict host-key checking.
- Read-only inspection is enabled by default.
- Service restart and raw shell are both disabled by default.
- Repositories and restartable services are allowlisted through environment variables.
- Output is capped, timed out, and passed through basic secret redaction before being returned.
- This sidecar must not be merged into, substituted for, or advertised as the canonical production `edge1-operator-mcp` tool surface.

## Appropriate use

Use this component only when an attended, explicitly authorized task cannot be completed through the canonical named Operator tools or another narrower approved interface. Examples include bounded repository/service diagnosis from an already-authorized SSH connector host or a narrowly scoped service restart when its environment and sudo allowlist have been deliberately enabled.

Do not attach this sidecar to the ordinary ChatGPT Edge1 custom app merely to gain generic command execution. `edge1_exec` being present here does not make generic shell part of the accepted production Operator contract.

## Requirements

- Node.js 20+
- OpenSSH client
- A working SSH alias `edge1` configured outside the repository
- A least-privilege remote account
- For service restart, only exact `sudo -n systemctl restart <allowlisted-service>` privileges for approved services

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
- `edge1_exec` (attended/policy-gated; disabled by default)

## ChatGPT architecture

For the permanent ChatGPT Operator, follow `docs/edge1-operator/14-secure-mcp-tunnel.md`: ChatGPT custom MCP app -> Secure MCP Tunnel -> loopback `edge1-operator-mcp`. Use `prompts/edge1-authenticated-operator.md` as the operator prompt.

Treat this SSH sidecar as a separate escalation path and keep it detached unless an attended task specifically needs it.
