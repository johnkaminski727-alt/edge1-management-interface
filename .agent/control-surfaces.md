# Edge1 Control Surfaces — Current State

Last reconciled: 2026-08-19  
Repository: `johnkaminski727-alt/edge1-management-interface`  
Workstream: Control Surfaces / exposure reduction / permanent private operator

## Current disposition

The Control Surfaces workstream is no longer at the 2026-08-18 pre-activation baseline. Public front-door/exposure-reduction work is accepted, the bounded Edge1 Operator MCP service is verified live on loopback, and the remaining incomplete portion is the private ChatGPT transport/attachment plus a small set of read-only diagnostic reconciliations.

## Public Edge1 behavior — accepted

The approved 2026-08-19 front-door cutover completed successfully.

Canonical ordinary public destination:

```text
https://ww.cx/time/
```

Accepted behavior includes:

- raw/default HTTP root -> 302 to WW.CX Time;
- exact `edge1.ww.cx` HTTPS root and `/index.html` -> 302 to WW.CX Time;
- existing HTTP-to-HTTPS named-host canonicalization preserved;
- `/edge1-status/` preserved;
- unknown/non-root paths not consumed by the front-door rule;
- raw HTTPS certificate/default-vhost behavior not weakened;
- PBX/SIP named-host behavior preserved;
- Apache TCP 80/443 and chronyd UDP 123/TCP 4460 ownership preserved.

Protected rollback evidence:

```text
/var/backups/wwcx-edge1-front-door-approved-20260819T052836Z
```

Acceptance record:

`docs/control-surfaces/edge1-front-door-live-acceptance-20260819.md`

HTTP 302 remains intentional; 308 promotion is deferred and separate.

## FreePBX Administration / UCP boundary

Earlier accepted Control Surfaces evidence records ordinary WAN FreePBX Administration/UCP access denied while approved private WireGuard/Tailscale paths remained available. The 2026-08-19 front-door change did not broaden those rules. Host-local/private-source acceptance preserved `/admin/` and `/ucp/` behavior for approved management paths.

The connected browser used for today's cache-busted front-door acceptance is part of the private management environment, so it is not independent WAN-denial evidence. Do not infer a new public exposure from private-path browser access.

Any future temporary/private native FreePBX session broker remains separately gated and must prove authentication/authorization, short expiry, revocation, CSRF, audit, redirect/cookie/WebSocket compatibility, CSP/X-Frame-Options handling, listener/firewall equivalence, and rollback before activation.

## Bounded Edge1 Operator — server side verified live

Fresh production verification from 2026-08-18 established:

- `edge1-operator-mcp.service` loaded, enabled, active, running;
- principal `edge1-operator`;
- MCP listener `127.0.0.1:8102` only;
- Operations API listener `127.0.0.1:8097` only;
- hardened service settings retained;
- bearer token metadata restricted and value not exposed;
- unauthenticated MCP request -> 401;
- authenticated initialize/tools/list -> 200;
- 16 named parameterless read-only tools discovered;
- `edge1.identity`, `edge1.health`, and `edge1.apache_status` succeeded;
- Operations API loopback true and `mutations_enabled=false`.

No generic `edge1.exec`, arbitrary command, URL, path, service, SQL, AMI/ARI command, or caller-selected Operations API action is exposed through this MCP surface.

## Secure MCP Tunnel staging

Non-secret host-side staging was accepted on 2026-08-18.

- compatible official `tunnel-client` already present and shared with Big Bird;
- Big Bird tunnel remained active and unchanged;
- Edge1 tunnel config/launcher/unit staged in an isolated namespace;
- `edge1-secure-mcp-tunnel.service` remained disabled/inactive;
- tunnel ID and runtime API key remained absent;
- no second tunnel process was started;
- no public listener, firewall, DNS, Apache proxy, MCP auth change, or Operator restart was introduced.

OpenAI guidance was rechecked on 2026-08-19 and still says private/on-prem MCP servers should use Secure MCP Tunnel rather than direct local/private connectivity.

## Remaining permanent-Operator gate

The incomplete path is now specifically:

```text
Authorized ChatGPT workspace/account
        |
Secure MCP Tunnel enrollment
        |
edge1-secure-mcp-tunnel service
        |
127.0.0.1:8102 edge1-operator-mcp
        |
16 reviewed read-only tools
```

Remaining acceptance tasks:

1. authorized human enables the applicable developer/custom-app capability;
2. authorized human creates/selects the Secure MCP Tunnel and provisions the tunnel ID/runtime API key locally on Edge1 without exposing them in chat/Git;
3. run tunnel doctor;
4. start the tunnel attended, still without persistence;
5. scan tools in ChatGPT and verify the exact expected 16-tool contract;
6. call `edge1.identity`, `edge1.health`, and approved diagnostics from ChatGPT;
7. verify durable Edge1 audit evidence and Big Bird/Operator listener equivalence;
8. test stop/disable plus account-side revocation procedure;
9. enable persistence only after all acceptance checks pass;
10. record final closeout.

No direct `edge1.*` MCP connector is exposed to the current ChatGPT session, so this gate remains incomplete.

## Remaining diagnostic reconciliation

Native Asterisk/Kamailio/FreePBX diagnostic cards have previously reported degraded/unavailable states through the Operations API while the higher-level telephony broker reported healthy. Reconcile those states from fresh read-only evidence only. Do not widen service account permissions or weaken hardening merely to make a diagnostic card green.

The existing Asterisk warning follow-up audit should also be run before any transport/listener/startup-policy conclusions are made.

## Current safe execution path

Until the private ChatGPT tunnel is attached, authenticated live work remains a human-relay path: ChatGPT prepares bounded commands, the authenticated operator runs them on Edge1, and output/evidence is returned for validation. Do not describe this as direct autonomous shell execution.

## Safety boundary

No credentials or secret values in chat/Git. No public MCP proxy. No new WAN management listener. No firewall/DNS/certificate/authentication changes, carrier routing, emergency-path change, call/message origination, or destructive action without the applicable explicit boundary and rollback evidence.
