# Edge1 Operator MCP Integration Status

Last reconciled: 2026-08-18
Status: bounded repository integration complete; production ChatGPT MCP attachment not yet directly verified

## Completed repository foundation

- Repository architecture and authority/risk boundaries.
- Loopback Edge1 Operations API with HMAC-SHA256 authentication, replay protection, audit logging, mutation gating, and a server-side fixed action allowlist.
- Fixed read-only Control Surfaces diagnostics and live-inventory tooling.
- Named MCP protocol/adapter contract with no generic `edge1.exec` capability.
- Bounded operator runtime that delegates only fixed read-only actions to the Operations API.
- Internal `tools/list` and `tools/call` dispatch wired through the adapter/runtime path.
- Focused tests that reject non-loopback Operations API URLs, arbitrary action names, MCP parameters, and mutating actions through the read-only tool surface.

The intended architecture remains:

```text
ChatGPT / authorized MCP client
        |
private authenticated transport
        |
edge1-operator-mcp service
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

The repository contract exposes:

- `edge1.identity`
- `edge1.health`
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

These tools accept no caller-controlled command, URL, port, path, service name, SQL, AMI/ARI command, or Operations API action name.

Mutating Operations API actions remain separately classified and are not reachable through this read-only MCP surface.

## Current access-path finding

Historical 2026-08-18 evidence showed an authenticated 1984 Hosting session with an active QEMU out-of-band console for `edge1.ww.cx`, but the browser connector could not type into the QEMU canvas. That remains historical evidence until rechecked.

A direct Edge1 Live Shell / permanent MCP connector is not considered available merely because repository source exists.

## Remaining integration work

1. Implement/review the production private MCP transport/attachment around the now-bounded tool contract.
2. Complete any installer/service hardening needed by that transport without creating a public management listener.
3. Run repository CI on the exact merged implementation revision.
4. Perform fresh Edge1 host installation, service, listener, log, and Operations API validation.
5. Attach the approved private ChatGPT workspace/tunnel transport.
6. Prove ChatGPT discovery plus successful identity/health and approved diagnostic calls.
7. Prove audit/evidence behavior and rollback before declaring the permanent operator complete.

## Historical installation note

`docs/edge1-operator/deployment-completion-record.md` preserves an earlier record that states `edge1-operator-mcp.service` was installed, enabled and active. Preserve it as historical evidence only. Current production claims require fresh authenticated host verification.

## Security boundary

Private credentials, HMAC material, provider session data and tunnel secrets remain outside Git and chat. The MCP layer must remain private and must not reintroduce generic execution authority.

## Completion condition

The permanent operator is complete only when the bounded repository implementation is validated on Edge1, reachable through the approved private transport, discoverable by the authorized ChatGPT client, able to execute the intended named tools with durable audit evidence, and recoverable through a documented rollback path.
