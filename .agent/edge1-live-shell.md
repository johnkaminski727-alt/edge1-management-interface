# Edge1 Live Shell MCP Connector

Last updated: 2026-08-18

## Objective

Provide ChatGPT and other approved MCP hosts with a guarded authenticated execution path to Edge1 without storing credentials in prompts, skills, or the repository.

## Implemented on feature branch

Branch: `feat/edge1-live-shell-connector`

Components:

- `tools/mcp/edge1-live-shell/package.json`
- `tools/mcp/edge1-live-shell/src/index.js`
- `tools/mcp/edge1-live-shell/README.md`
- `prompts/edge1-authenticated-operator.md`
- `.github/workflows/edge1-live-shell.yml`

Exposed MCP tools:

- `edge1_connection_test`
- `edge1_inspect`
- `edge1_restart_service`
- `edge1_exec`

## Default policy

- SSH alias: `edge1`
- strict host-key checking: enabled
- batch authentication: enabled
- service restarts: disabled
- raw shell: disabled
- default allowed service: `bigbird-ai-gateway`
- repository aliases: `edge1-interface` and `bigbird-gateway`
- command timeout: 30 seconds, capped at 120 seconds
- stdout/stderr cap: 24 KiB by default
- basic secret redaction before MCP return

## Validation

Local syntax validation performed with:

```text
node --check src/index.js
```

Result: PASS.

Full dependency install and MCP Inspector validation were not executable in the current isolated runtime because outbound DNS/network access was unavailable. CI has been added to install dependencies and verify MCP SDK imports on GitHub-hosted runners.

## Not yet performed

No live Edge1 connection, SSH configuration, credential/key change, sudo change, firewall change, DNS change, production service restart, deployment, or ChatGPT MCP attachment was performed by this branch.

## Remaining operator setup

1. Provide an external SSH configuration entry named `edge1` using the approved least-privilege account and verified host key.
2. If restarts are desired, grant only exact non-interactive sudo commands for explicitly allowlisted services.
3. Install connector dependencies on the MCP connector host.
4. Attach the connector to the approved MCP host/private tunnel mechanism.
5. Run `edge1_connection_test` and verify hostname/principal before any other operation.
6. Keep `EDGE1_ALLOW_RESTARTS=0` and `EDGE1_ENABLE_RAW_SHELL=0` until a specific attended task requires them.
