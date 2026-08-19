# Edge1 Operator MCP Integration Status

Last reconciled: 2026-08-19  
Status: bounded production MCP service verified on Edge1; Secure MCP Tunnel staging and local credential provisioning complete; fail-closed preactivation and private ChatGPT attachment remain

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
Secure MCP Tunnel                <-- final attachment/acceptance gate
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

## Secure MCP Tunnel direction

The accepted direction remains to keep `edge1-operator-mcp` loopback-only and use Secure MCP Tunnel for the private ChatGPT attachment. Do not add an Apache public MCP proxy, WAN MCP listener, firewall opening, or authentication weakening as a substitute.

## Host-side tunnel state

Non-secret Edge1 tunnel assets were staged and accepted on 2026-08-18. By 2026-08-19 the authorized account-side tunnel selection and local credential provisioning were also complete without exposing secret values.

Current state:

- Edge1 tunnel config/launcher/unit installed;
- `edge1-secure-mcp-tunnel.service` disabled/inactive;
- `/etc/edge1-tunnel/tunnel-id` present with restricted metadata;
- `/etc/edge1-tunnel/runtime-api-key` present with restricted metadata;
- existing official shared `tunnel-client` retained unchanged;
- Big Bird tunnel remains accepted and must not be disrupted;
- no accepted Edge1 tunnel process yet;
- no public MCP listener or proxy.

Installed tunnel-client identity:

```text
0.0.10+105e17a79a36e4e5c897fd698ed2b8dbf935b144
sha256=937347720ef32ef3ef2f68f4496b2dd7917ca5e575452ed87a4ce78d0262a100
```

Its raw doctor returns exit code `2` with only `oauth_metadata` failing on an expected HTTP 404. This is a reviewed old-client doctor behavior for the Edge1 bearer-authenticated non-OAuth MCP endpoint, not a reason to add fake OAuth metadata or upgrade the shared binary merely to make doctor green.

The required preactivation command is the repository compatibility validator:

```sh
sudo -u edge1-operator \
  /opt/edge1-management-interface/deploy/edge1-tunnel/validate-edge1-secure-mcp-tunnel-doctor.sh
```

Require:

```text
EDGE1_TUNNEL_COMPAT_DOCTOR=PASS
```

The hardened validator fails closed unless the reviewed client and installed tunnel assets match their expected hashes/metadata, the bearer boundary still returns unauthenticated 401 and authenticated GET 405, the OAuth metadata candidates remain 404, and raw doctor still has exactly the reviewed single failure. Unexpected raw success from the pinned client is drift requiring re-review.

The staging installer is also non-disruptive: `--apply` refuses when `edge1-secure-mcp-tunnel.service` is already active or enabled instead of stopping/disabling an accepted tunnel.

See:

- `docs/edge1-operator/14-secure-mcp-tunnel.md`
- `docs/edge1-operator/15-tunnel-doctor-compatibility-20260819.md`

## Remaining integration work

- Merge the preactivation hardening only after exact-head CI is green and fast-forward the clean Edge1 checkout.
- Run the compatibility validator and require `EDGE1_TUNNEL_COMPAT_DOCTOR=PASS`.
- Obtain explicit approval for attended activation.
- Start tunnel attended without persistence.
- Verify its dynamic loopback health/readiness, Big Bird health, and Edge1 listener equivalence.
- Scan tools from ChatGPT; require exact 16-tool contract and no generic execution tool.
- Prove ChatGPT-side `edge1.identity` and `edge1.health`.
- Prove approved read-only diagnostic calls and durable audit evidence.
- Test attended stop and account-side tunnel/key revocation.
- Enable persistence only after attended acceptance passes.
- Record final closeout.

No direct `edge1.*` MCP connector is exposed to the current ChatGPT session, so the private ChatGPT attachment remains incomplete.

## Related production state

The Edge1 public front door is LIVE / ACCEPTED with canonical ordinary public destination `https://ww.cx/time/`. This is independent of the private MCP transport and must not be used as a reason to expose the Operator over Apache/public HTTPS.

Read-only security-boundary classification, the corrected Control Surfaces inventory, and the corrected Asterisk audit remain safe independent work before activation.

## Security boundary

Private credentials, HMAC material, MCP bearer material, provider session data, tunnel IDs, runtime API keys, and tunnel secrets remain outside Git/chat/evidence. The MCP layer remains private and must not reintroduce generic execution authority.

## Completion condition

The permanent Operator is complete only when the verified bounded Edge1 MCP service is reachable through the approved private ChatGPT tunnel, discoverable by the authorized ChatGPT client, able to execute the intended named tools with durable audit evidence, and recoverable through documented attended stop and account-side revocation paths.
