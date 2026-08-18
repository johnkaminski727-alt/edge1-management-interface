# Edge1 Live Shell MCP Sidecar

Last updated: 2026-08-18

## Status

The SSH-backed connector from PR #429 is merged on `main`, but subsequent reconciliation confirmed it is **not** the canonical production ChatGPT Edge1 Operator.

The repository already contains a more mature production Operator implementation under `server/edge1_operator_*` and `docs/edge1-operator/`. Fresh production evidence recorded on 2026-08-18 establishes `edge1-operator-mcp.service` as live, hardened, bearer-protected and loopback-only, backed by the authenticated Operations API. Its reviewed production MCP contract is named/bounded and intentionally excludes generic shell execution.

The permanent ChatGPT path remains:

```text
ChatGPT custom MCP app
        |
OpenAI Secure MCP Tunnel
        |
Edge1
        |
127.0.0.1:8102 edge1-operator-mcp
        |
127.0.0.1:8097 Operations API
```

Host-side non-secret Secure MCP Tunnel staging is already accepted in `docs/edge1-operator/14-secure-mcp-tunnel.md`. The remaining permanent-attachment gate is account/workspace tunnel enrollment and secret provisioning, followed by ChatGPT-side tool discovery and acceptance. Those credential/account steps remain human boundaries.

## Role of `tools/mcp/edge1-live-shell`

Retain the component as an **attended escalation/fallback sidecar** only. It wraps an externally configured SSH alias and is useful when a specifically authorized task cannot be completed through the production named Operator tools or another narrower interface.

Sidecar tools:

- `edge1_connection_test`
- `edge1_inspect`
- `edge1_restart_service`
- `edge1_exec`

The sidecar is not part of the canonical production Operator contract and should not be attached to the ordinary ChatGPT Edge1 custom app merely to expose generic command execution.

## Default sidecar policy

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

## Additional live evidence found during reconciliation

Authenticated WW.CX Operations Center/browser telemetry is currently reachable and reports the Operations API as healthy with its fixed read-only catalog. Recent Operations Center logs also show successful public-key SSH sessions from the management network, so there is evidence of an existing SSH trust path; no new SSH key, firewall opening, public listener, or alternate trust path should be created merely to support this sidecar.

Browser/Operations Center evidence is a read-only secondary observation path. It does not replace MCP identity checks for final ChatGPT Operator acceptance.

## Validation

PR #429 CI passed before merge, including the Edge1 Live Shell Connector workflow. The connector source passed Node syntax validation. No SSH credential, sudo policy, firewall, DNS, production listener, or Edge1 service was changed by PR #429.

## Current continuation order

1. Prefer the canonical production `edge1-operator-mcp` and its named tool contract.
2. Complete Secure MCP Tunnel account/workspace enrollment only at the authorized human credential boundary.
3. From ChatGPT, scan the production tools and prove `edge1.identity` and `edge1.health`.
4. Run approved named diagnostics and verify durable evidence/audit behavior.
5. Keep `edge1-live-shell` detached and both mutation flags off unless a specific attended escalation requires it.
6. Do not expose MCP publicly and do not alter DNS, firewall, Apache, SSH trust, or Operator authentication to bypass the tunnel/account gate.
