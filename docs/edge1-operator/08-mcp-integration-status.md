# Edge1 Operator MCP Integration Status

Last reconciled: 2026-08-18
Status: bounded production MCP service verified on Edge1; private ChatGPT transport/attachment remains the final integration gate

## Completed repository and live foundation

- Loopback Edge1 Operations API with HMAC-SHA256 authentication, replay protection, audit logging, mutation gating, and a server-side fixed action allowlist.
- Fixed read-only Control Surfaces diagnostics and live-inventory tooling.
- Named MCP protocol/adapter contract with no generic `edge1.exec` capability.
- Bounded operator runtime that delegates only fixed read-only actions to the Operations API.
- Internal `tools/list` and `tools/call` dispatch wired through the adapter/runtime path.
- Focused tests that reject non-loopback Operations API URLs, arbitrary action names, MCP parameters, and mutating actions through the read-only tool surface.
- Fresh production verification on 2026-08-18 confirmed `edge1-operator-mcp.service` is installed, enabled and active.
- The production service runs as `edge1-operator` and binds only to `127.0.0.1:8102`.
- The service retains `NoNewPrivileges=true`, `PrivateTmp=true`, `ProtectSystem=strict`, `ProtectHome=true`, and repository/config read-only paths.
- The bearer token file exists outside Git, is owned by `edge1-operator`, and was verified mode `0600`; token content was not displayed or stored.
- Unauthenticated `GET /mcp` returns HTTP 401.
- Authenticated MCP `initialize`, `tools/list`, `edge1.identity`, `edge1.health`, and `edge1.apache_status` calls returned HTTP 200.
- `edge1.identity` reported hostname `edge1.ww.cx`, principal `edge1-operator`, service ready.
- `edge1.health` reported the loopback Operations API healthy with 27 actions and `mutations_enabled=false`.

The architecture is therefore live through the private Edge1 service boundary:

```text
ChatGPT / authorized MCP client
        |
private authenticated transport   <-- remaining attachment gate
        |
edge1-operator-mcp service (127.0.0.1:8102)
        |
named typed read-only MCP tools
        |
loopback HMAC/replay-protected Edge1 Operations API
        |
fixed server-side actions
        |
Edge1 services and repositories
```

## MCP-visible read-only tools

Fresh `tools/list` returned 16 parameterless tools:

- `edge1.identity`
- `edge1.health`
- `edge1.snapshot`
- `edge1.inventory`
- `edge1.services`
- `edge1.network_state`
- `edge1.disk_state`
- `edge1.bigbird_status`
- `edge1.operations_status`
- `edge1.apache_status`
- `edge1.asterisk_status`
- `edge1.telephony_status`
- `edge1.messaging_status`
- `edge1.time_authority_status`
- `edge1.git_state`
- `edge1.config_digest`

These tools accept no caller-controlled command, URL, port, path, service name, SQL, AMI/ARI command, Operations API action name, or tool parameters.

Mutating Operations API actions remain separately classified and are not reachable through this MCP surface.

## Production transport decision

OpenAI's current ChatGPT guidance states that ChatGPT does not directly connect to a local/private-network MCP server. For a private-network or on-premises MCP server, use **Secure MCP Tunnel** rather than exposing the server to the public internet.

Reference: OpenAI Help Center, `Developer mode and MCP apps in ChatGPT`.

Accordingly, the approved completion direction is:

1. Keep `edge1-operator-mcp` loopback-only on `127.0.0.1:8102`.
2. Do not add an Apache public proxy or new WAN management listener for MCP.
3. Enable the applicable ChatGPT developer/custom-app capability in the authorized workspace/account.
4. Use Secure MCP Tunnel to bridge the private Edge1 MCP endpoint to ChatGPT.
5. Scan the tools and verify the frozen/discovered tool contract matches the 16 named parameterless tools above.
6. Test `edge1.identity`, `edge1.health`, and approved diagnostics from ChatGPT.
7. Verify Edge1 audit evidence and tunnel rollback/revocation before declaring completion.

Any account sign-in, developer-mode enablement, connector activation token, private tunnel enrollment material, or equivalent secret remains a human credential/activation boundary and must not be pasted into Git or chat.

## Remaining integration work

- Complete the Secure MCP Tunnel / ChatGPT custom-app attachment through the authorized account/workspace UI.
- Prove ChatGPT-side discovery and successful identity/health calls.
- Prove approved diagnostic calls and durable audit/evidence behavior through that permanent connection.
- Record tunnel/service rollback and revocation procedure without recording secret values.

## Security boundary

Private credentials, HMAC material, MCP bearer material, provider session data and tunnel secrets remain outside Git and chat. The MCP layer remains private and must not reintroduce generic execution authority.

## Completion condition

The permanent operator is complete only when the currently verified bounded Edge1 MCP service is reachable through the approved Secure MCP Tunnel/private ChatGPT transport, discoverable by the authorized ChatGPT client, able to execute the intended named tools with durable audit evidence, and recoverable through a documented rollback/revocation path.
