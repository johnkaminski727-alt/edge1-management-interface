# Edge1 Live Shell MCP Connector

A guarded MCP bridge for authenticated Edge1 operations. It wraps an existing SSH alias named `edge1` and exposes narrow read-first tools to an MCP host.

## Security model

- No credentials, private keys, tokens, hostnames, or private addresses are stored here.
- SSH uses `BatchMode=yes` and strict host-key checking.
- Read-only inspection is enabled by default.
- Service restart and raw shell are both disabled by default.
- Repositories and restartable services are allowlisted through environment variables.
- Output is capped, timed out, and passed through basic secret redaction before being returned.

## Requirements

- Node.js 20+
- OpenSSH client
- A working SSH alias `edge1` configured outside the repository
- The remote account should be least privilege. If service restart is enabled, grant only exact `sudo -n systemctl restart <allowlisted-service>` permissions.

## Install and test

```sh
cd tools/mcp/edge1-live-shell
npm install
npm run check
npx @modelcontextprotocol/inspector node src/index.js
```

Run `edge1_connection_test` first. It should return the verified Edge1 hostname and authenticated principal.

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

## MCP tools

- `edge1_connection_test`
- `edge1_inspect`
- `edge1_restart_service` (policy-gated)
- `edge1_exec` (attended/policy-gated)

## ChatGPT connection

Attach this server through the supported private MCP connection method for the ChatGPT workspace. Once attached, use the operator prompt in `prompts/edge1-authenticated-operator.md`.
