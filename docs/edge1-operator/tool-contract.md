# Edge1 Operator Tool Contract

## Public MCP surface

The public Edge1 Operator MCP surface is defined only by
`server/edge1_operator_mcp_protocol.py`. Internal adapter capabilities do not become
public merely because implementation code exists.

Public read tools include the existing Edge1 identity/health/snapshot/inventory,
service/network/disk, BigBird, Apache, Asterisk, Telephony, Messaging, time,
repository and configuration-digest tools plus:

- `edge1.capabilities` -- returns the sanitized versioned capability manifest and
  whether the current operator process has each required scope;
- `edge1.telephony_console_control_status` -- returns sanitized preconditions for
  the bounded Telephony Console reload: current PID, reviewed source SHA-256,
  repository HEAD and loopback health.

The first public host-control write is:

- `edge1.telephony_console_reload` -- restarts only
  `wwcx-telephony-console.service`, a loopback read-only operations console. The
  request must include the exact PID, source SHA-256 and repository HEAD returned
  by the read-before-write control snapshot plus an idempotency key. It cannot
  select another service, command, path, URL, carrier, route or dialplan.

## Capability manifest

`config/edge1-operator-capabilities.json` is the versioned source policy. Every
public tool belongs to exactly one capability. A tool call is allowed only when:

1. the tool is in the static public MCP contract;
2. the tool is assigned in the capability manifest;
3. that capability is enabled; and
4. the operator process has the capability's `required_scope`.

This is deliberately two-dimensional. Enabling a capability does not grant its
scope, and granting a scope does not bypass a disabled capability.

Default process scopes are read-only (`edge1.status.read`, `edge1.telephony.read`,
`edge1.messaging.read`). The write scope `edge1.telephony.control.safe` must be
explicitly configured through the deployed operator service environment before the
reload tool can execute.

## Operations API privileged broker

Host mutation still occurs only through the loopback Edge1 Operations API. The
operator runtime never executes arbitrary commands itself.

The Operations API supports the existing fixed parameterless actions and a new
fixed typed-action path. Typed actions:

- must be named in `config/edge1-operations-allowlist.json`;
- map to repository-controlled handler names, not caller-supplied argv;
- accept JSON only through a handler-specific strict schema;
- remain subject to `EDGE1_OPS_MUTATIONS_ENABLED`;
- are HMAC-authenticated and nonce/replay protected;
- are audited using a body hash rather than secret-bearing parameters;
- use durable action+idempotency-key replay/conflict protection.

The first typed handler is `telephony_console_reload`. Its caller cannot supply a
service name, filesystem path, command, URL, SQL, shell fragment or environment
value.

## Telephony Console reload guarantees

Before restart the broker verifies:

- `wwcx-telephony-console.service` is active;
- Asterisk and the Messaging Gateway are active;
- current Telephony Console PID exactly matches the caller's inspected PID;
- source SHA-256 exactly matches the inspected digest;
- repository HEAD exactly matches the inspected commit.

After restart it verifies the console is active and healthy and that Asterisk and
Messaging Gateway PIDs did not change. No call, SIP OPTIONS probe, SMS/MMS, carrier
contact, route change, dialplan change, quarantine release or public-listener change
is part of this control. If verification fails, the broker performs a bounded
recovery restart of the same reviewed console unit; no configuration was changed by
the action.

## Internal agent coordination

`agent.turn.status` and `agent.turn.handoff` remain internal coordination
capabilities implemented by the adapter/turn-state store. They are intentionally
**not** members of `PUBLIC_EDGE1_TOOL_NAMES` and therefore are not published by the
production public Edge1 Operator entrypoint.

Their SQLite turn-ownership and idempotency behavior remains unchanged. This
separation prevents agent-coordination state from being confused with host-control
authority.

## Safety boundary

The public Operator does not expose generic shell execution, arbitrary `sudo`,
arbitrary `systemctl`, arbitrary SQL, arbitrary files, arbitrary HTTP targets, or a
global host-write tool. PBX, Messaging, carrier, mail, security and infrastructure
mutations must each receive purpose-built named capabilities with independent
preconditions, scopes, verification and rollback/recovery policy.

Secrets and private credentials are never returned through the tool surface.
