# Edge1 Operator Completion Status

Last reconciled: 2026-08-18

## Purpose

Track the transition from repository architecture work to a permanently available, private, authenticated ChatGPT Edge1 operator.

## Repository work completed

- Architecture definition.
- Authority and risk boundaries.
- Loopback HMAC/replay-protected Operations API and server-side allowlist.
- Fixed non-mutating Control Surfaces diagnostics.
- Read-only Control Surfaces live-inventory runner with safety-contract tests and CI.
- Named, parameterless MCP read-only tool contract.
- Fixed Operations API client restricted to loopback and a compile-time action set.
- Runtime mappings from named MCP tools to fixed read-only Operations API actions.
- `tools/list` / `tools/call` internal dispatch path.
- Removal of the legacy MCP-visible generic `edge1.exec` contract and generic `run_bounded(command)` scaffold.
- Focused source validation for bounded-tool behavior.

## Fresh production state verified 2026-08-18

The live Edge1 operator service is no longer historical-only evidence:

- `edge1-operator-mcp.service` is loaded, enabled, active and running.
- Service principal: `edge1-operator`.
- Working runtime is hardened with `NoNewPrivileges`, `PrivateTmp`, `ProtectSystem=strict`, and `ProtectHome=true`.
- MCP listener: `127.0.0.1:8102` only.
- Operations API listener: `127.0.0.1:8097` only.
- MCP bearer token metadata verified owner `edge1-operator`, mode `0600`; value not exposed.
- Unauthenticated MCP request returned HTTP 401.
- Authenticated MCP initialize and tool-list requests returned HTTP 200.
- Fresh tool discovery returned 16 named parameterless read-only tools.
- `edge1.identity` returned `edge1.ww.cx`, principal `edge1-operator`, status ready.
- `edge1.health` returned operator status ok and Operations API health ok with 27 actions, loopback true and `mutations_enabled=false`.
- `edge1.apache_status` returned a successful bounded read-only Apache status action.

This establishes the production server-side MCP boundary as **verified live**.

## Current execution-path status

The remaining incomplete portion is the private ChatGPT-side transport/attachment.

OpenAI's current ChatGPT guidance says local/private-network MCP servers are not connected directly; private/on-premises servers should use **Secure MCP Tunnel** so the MCP server does not need to be exposed to the public internet.

Therefore the intended transport is now explicitly:

```text
ChatGPT custom MCP app
        |
Secure MCP Tunnel
        |
Edge1 private host
        |
127.0.0.1:8102 edge1-operator-mcp
```

No Apache public MCP proxy, WAN MCP listener, or firewall opening is part of the completion plan.

## Remaining completion tasks

- Enable the applicable ChatGPT developer/custom-app capability using the authorized account/workspace UI.
- Enroll Secure MCP Tunnel for the Edge1 loopback MCP service without disclosing enrollment/token material in chat or Git.
- Scan/discover the 16 MCP tools from ChatGPT and verify the contract.
- Prove ChatGPT-side `edge1.identity` and `edge1.health` calls.
- Prove approved diagnostics and audit/evidence behavior through the permanent connector.
- Record tunnel rollback/revocation procedure and complete final closeout.

Account sign-in, developer-mode enablement, private activation links, tunnel enrollment secrets, and equivalent credential material remain explicit human boundaries.

## Other Control Surfaces state

The public Edge1 web exposure-reduction work is accepted and repository-reconciled: ordinary root traffic redirects to `https://creekco.ca/time/`, WAN FreePBX Administration/UCP access is denied, and approved private WireGuard/Tailscale paths remain available. The WW.CX Operations Center Control Surfaces page is deployed and authenticated-browser verified.

Asterisk/Kamailio/FreePBX native CLI diagnostic cards currently report degraded/unavailable states through the Operations API while the higher-level telephony broker reports healthy. This is being reconciled without weakening service hardening or widening account permissions.

## Archive state

Repository documentation is now a current sanitized checkpoint. The operator workstream remains **active / incomplete only at the ChatGPT private-transport attachment and final diagnostic reconciliation gates**.

## Operating rule

Routine engineering work continues without repeated approval requests under the standing authorization. Credentials, secret material, irreversible/destructive changes, legal/commercial commitments, privileged network/security changes, and other explicit stop conditions remain gated.
