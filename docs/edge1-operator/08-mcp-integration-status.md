# Edge1 Operator MCP Integration Status

Last reconciled: 2026-08-19  
Status: bounded production MCP service verified on Edge1; non-secret tunnel staging accepted; private ChatGPT transport/attachment remains the final integration gate

## Completed live foundation

- Loopback Edge1 Operations API with HMAC-SHA256 authentication, replay protection, audit logging, mutation gating, and fixed server-side allowlist.
- Fixed read-only Control Surfaces diagnostics and live-inventory tooling.
- Named MCP protocol/adapter contract with no generic `edge1.exec` capability.
- Bounded runtime delegates only fixed read-only actions to the Operations API.
- Internal `tools/list` and `tools/call` dispatch wired through the reviewed adapter/runtime path.
- Tests reject non-loopback Operations API URLs, arbitrary action names, MCP parameters, and mutating actions through the read-only surface.
- Production `edge1-operator-mcp.service` verified installed, enabled, active.
- Service principal `edge1-operator`; listener `127.0.0.1:8102` only.
- Operations API `127.0.0.1:8097` only.
- Hardened systemd boundary retained.
- Bearer token file remains outside Git with restricted ownership/mode; value not displayed or stored.
- Unauthenticated `GET /mcp` -> HTTP 401.
- Authenticated MCP initialize/tools/list/identity/health/Apache-status -> HTTP 200.
- `edge1.identity` reported expected Edge1 identity and ready state.
- `edge1.health` reported loopback Operations API healthy with mutations disabled.

The architecture is live through the private Edge1 service boundary:

```text
ChatGPT / authorized MCP client
        |
private authenticated transport   <-- remaining attachment gate
        |
edge1-operator-mcp (127.0.0.1:8102)
        |
16 named typed read-only MCP tools
        |
loopback HMAC/replay-protected Operations API
        |
fixed server-side actions
```

## MCP-visible read-only tools

The reviewed contract contains exactly these 16 parameterless tools:

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

They accept no caller-controlled command, URL, port, path, service name, SQL, AMI/ARI command, Operations API action name, or tool parameters. Mutating Operations API actions are not reachable through this MCP surface.

## Secure MCP Tunnel decision — reverified 2026-08-19

OpenAI's current ChatGPT help guidance continues to state that ChatGPT does not directly connect to a local/private-network MCP server. Private/on-premises MCP servers should use **Secure MCP Tunnel** instead of being exposed to the public internet.

Accordingly, the approved direction remains:

1. keep `edge1-operator-mcp` loopback-only on `127.0.0.1:8102`;
2. do not add an Apache public MCP proxy, WAN MCP listener, firewall opening, or authentication weakening;
3. use the authorized ChatGPT developer/custom-app capability;
4. bridge Edge1 with Secure MCP Tunnel;
5. scan and verify the frozen/discovered 16-tool contract;
6. prove identity/health/approved diagnostics from ChatGPT;
7. prove durable audit evidence and rollback/revocation before persistence/final completion.

## Host-side tunnel staging — accepted

The non-secret Edge1 tunnel assets were staged and accepted on 2026-08-18. The compatible existing official `tunnel-client` was retained unchanged, Big Bird's active tunnel remained untouched, and the Edge1 tunnel runtime was isolated.

Current intended pre-enrollment state:

- Edge1 tunnel config/launcher/unit installed;
- `edge1-secure-mcp-tunnel.service` disabled/inactive;
- tunnel ID absent;
- runtime API key absent;
- no second tunnel process;
- no public listener or proxy.

See `docs/edge1-operator/14-secure-mcp-tunnel.md` for exact staging evidence and the credential/doctor/attended-activation sequence.

## Remaining integration work

- Authorized human/account boundary: enable developer/custom-app capability and create/select the Secure MCP Tunnel.
- Provision tunnel ID and runtime API key locally on Edge1 without exposing values.
- Run doctor.
- Start tunnel attended without persistence.
- Scan tools from ChatGPT; require exact 16-tool contract and no generic execution tool.
- Prove ChatGPT-side `edge1.identity` and `edge1.health`.
- Prove approved read-only diagnostic calls and durable audit evidence.
- Verify Big Bird tunnel and Edge1 listener equivalence.
- Test stop/disable and account-side tunnel/key revocation.
- Enable persistence only after attended acceptance passes.
- Record final closeout.

No direct `edge1.*` MCP connector is exposed to the current ChatGPT session, so the private ChatGPT attachment remains incomplete.

## Related 2026-08-19 production state

The Edge1 public front door is now LIVE / ACCEPTED with canonical ordinary public destination `https://ww.cx/time/`. This is independent of the private MCP transport and must not be used as a reason to expose the Operator over Apache/public HTTPS.

## Security boundary

Private credentials, HMAC material, MCP bearer material, provider session data, tunnel IDs, runtime API keys, and tunnel secrets remain outside Git/chat/evidence. The MCP layer remains private and must not reintroduce generic execution authority.

## Completion condition

The permanent Operator is complete only when the verified bounded Edge1 MCP service is reachable through the approved private ChatGPT tunnel, discoverable by the authorized ChatGPT client, able to execute the intended named tools with durable audit evidence, and recoverable through documented stop/disable and account-side revocation paths.
