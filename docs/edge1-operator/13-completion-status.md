# Edge1 Operator Completion Status

Last reconciled: 2026-08-19

## Purpose

Track the transition from the verified live Edge1 server-side Operator to a permanently available private authenticated ChatGPT Edge1 operator.

## Repository and server-side foundation — complete

The following are complete and must not be rebuilt merely because the ChatGPT attachment remains pending:

- architecture and authority/risk boundaries;
- loopback HMAC/replay-protected Operations API and fixed server-side allowlist;
- fixed non-mutating Control Surfaces diagnostics;
- read-only Control Surfaces live-inventory runner with safety tests and CI;
- named parameterless MCP read-only tool contract;
- fixed Operations API client restricted to loopback and compile-time actions;
- runtime mappings from MCP tools to fixed read-only Operations API actions;
- internal `tools/list` / `tools/call` dispatch;
- removal of MCP-visible generic `edge1.exec` and generic arbitrary-command execution scaffolding;
- focused bounded-tool validation.

Fresh production verification on 2026-08-18 established:

- `edge1-operator-mcp.service` loaded, enabled, active, running;
- service principal `edge1-operator`;
- MCP listener `127.0.0.1:8102` only;
- Operations API listener `127.0.0.1:8097` only;
- hardened service settings retained (`NoNewPrivileges`, `PrivateTmp`, `ProtectSystem=strict`, `ProtectHome=true`);
- bearer token metadata restricted; token value not exposed;
- unauthenticated MCP request -> HTTP 401;
- authenticated initialize/tools/list -> HTTP 200;
- 16 named parameterless read-only tools discovered;
- `edge1.identity`, `edge1.health`, and `edge1.apache_status` succeeded;
- Operations API reported loopback true and `mutations_enabled=false`.

The production server-side MCP boundary is therefore **verified live**.

## Public Edge1 state — updated 2026-08-19

The public front-door work is now LIVE / ACCEPTED.

Canonical ordinary public destination:

```text
https://ww.cx/time/
```

Raw/default HTTP root and exact named Edge1 HTTPS root behavior were accepted with HTTP 302 while operational/non-root routes, PBX/SIP behavior, Apache listeners, and chronyd NTP/NTS listeners remained preserved.

Protected rollback evidence:

```text
/var/backups/wwcx-edge1-front-door-approved-20260819T052836Z
```

Acceptance record:

`docs/control-surfaces/edge1-front-door-live-acceptance-20260819.md`

HTTP 302 remains intentional; 308 promotion is separate optional work.

## Secure MCP Tunnel — non-secret staging complete

Host-side non-secret staging was accepted on 2026-08-18:

- compatible existing official `tunnel-client` retained unchanged;
- Big Bird tunnel remained active/unchanged;
- Edge1 tunnel config, launcher, and unit staged in a separate namespace;
- `edge1-secure-mcp-tunnel.service` intentionally disabled/inactive;
- tunnel ID and runtime API key absent;
- no second tunnel process started;
- no public listener, firewall/DNS change, Apache proxy, MCP auth change, or Operator restart performed.

OpenAI guidance was rechecked on 2026-08-19 and still states that local/private-network MCP servers are not connected directly; private/on-premises MCP should use Secure MCP Tunnel rather than exposing the MCP service publicly.

## Remaining completion gate — ChatGPT private attachment

The remaining path is:

```text
ChatGPT custom MCP app
        |
Secure MCP Tunnel
        |
Edge1 private host
        |
127.0.0.1:8102 edge1-operator-mcp
```

Remaining tasks:

1. authorized workspace/account operator enables the applicable developer/custom-app capability;
2. create/select the Secure MCP Tunnel and provision its tunnel ID/runtime API key locally on Edge1 without exposing secret values;
3. run tunnel doctor;
4. start the tunnel attended without enabling persistence;
5. scan tools from ChatGPT and verify exactly the expected 16 named parameterless read-only tools;
6. prove ChatGPT-side `edge1.identity`, `edge1.health`, and approved diagnostics;
7. verify durable Edge1 audit evidence and Big Bird/Operator listener equivalence;
8. test service stop/disable plus account-side revocation path;
9. enable persistence only after attended acceptance passes;
10. record final closeout.

Account sign-in, developer-mode enablement, private activation links, tunnel enrollment values, runtime API keys, and equivalent credential material remain explicit human boundaries and must not be pasted into Git or chat.

No direct `edge1.*` MCP connector is exposed to the current ChatGPT session, so the private attachment gate is not yet complete.

## Remaining diagnostic reconciliation

Native Asterisk/Kamailio/FreePBX diagnostic cards have previously reported degraded/unavailable states while higher-level telephony health was healthy. Reconcile these from fresh read-only evidence without weakening service hardening or widening account permissions.

The existing `tools/alerting/asterisk_warning_followup_audit.sh` should also be run to resolve the recorded PJSIP transport visibility, boot-persistence, and TCP 8089 questions before any related configuration decision.

## Completion condition

The permanent Operator is complete only when the verified loopback MCP service is reachable through the approved Secure MCP Tunnel/private ChatGPT transport, ChatGPT discovers the exact reviewed bounded tools, identity/health and approved diagnostics succeed with durable audit evidence, rollback/revocation is proven, and no secret or new public management exposure has been introduced.

## Operating rule

Routine repository work and read-only inspection continue under standing authorization. Credentials/secret material, irreversible/destructive changes, privileged network/security changes, live carrier/call/message behavior, and other explicit stop conditions remain gated.
