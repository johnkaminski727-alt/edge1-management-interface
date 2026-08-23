# Edge1 Operator Controls v1 — 2026-08-23

## Purpose

Introduce a capability-scoped public host-control plane for the authenticated Edge1
Operator without adding generic shell, arbitrary systemd control, or a global write
switch.

## Source state

This increment adds:

- `config/edge1-operator-capabilities.json` and schema;
- `edge1.capabilities` public read tool;
- `edge1.telephony_console_control_status` read-before-write precondition tool;
- `edge1.telephony_console_reload` first bounded public write tool;
- typed Operations API action support with durable audit and crash-safe idempotency;
- independent `telephony_safe_controls` broker mutation gate;
- strict separation of public `edge1.*` host tools from internal `agent.turn.*`
  coordination tools.

## Three independent write gates

The Telephony Console reload can execute only when all three layers allow it:

1. static public MCP contract contains `edge1.telephony_console_reload`;
2. capability `edge1.telephony.control.safe` is enabled and the Operator process has
   scope `edge1.telephony.control.safe`;
3. Operations API gate `EDGE1_OPS_TELEPHONY_SAFE_CONTROLS_ENABLED=true` is active.

The legacy `EDGE1_OPS_MUTATIONS_ENABLED` gate remains independent and may remain
`false`. Enabling the Telephony safe-control gate must not enable repository,
security, or other legacy mutation actions.

## Read-before-write protocol

The agent first calls `edge1.telephony_console_control_status`. The returned
sanitized values are the only accepted preconditions:

- current Telephony Console PID;
- SHA-256 of `server/telephony_status_server.py`;
- repository HEAD;
- loopback health state.

A reload request supplies the PID/digest/HEAD exactly plus a fresh idempotency key.
The fixed Operations API handler rechecks all values immediately before restart.
Stale values fail closed.

## Idempotency

Typed actions claim `(action, idempotency_key)` atomically in the Operations API
SQLite database before execution.

- identical completed request: replay stored result;
- same key with changed request body: conflict;
- same key while execution is in progress, or after an interrupted execution left an
  incomplete claim: fail closed and require state reconciliation before a new key;
- no second execution occurs merely because a caller retries after losing a response.

## Telephony Console mutation boundary

The handler is hard-coded to `wwcx-telephony-console.service` and does not accept a
service name. It verifies Asterisk and Messaging Gateway are active before mutation
and verifies their PIDs are unchanged afterward. It verifies Telephony Console health
after restart.

The tool cannot receive or derive arbitrary:

- service names;
- commands/argv;
- paths;
- URLs/hosts/ports;
- environment variables;
- SQL;
- carrier/provider identifiers;
- routes, dialplan, numbers, recipients, or message contents.

No call, SIP OPTIONS probe, SMS/MMS, carrier contact, quarantine release, routing
change or public-listener change is part of this action.

## Deployment posture

Repository/source defaults remain fail closed:

- `EDGE1_OPS_MUTATIONS_ENABLED=false`;
- `EDGE1_OPS_TELEPHONY_SAFE_CONTROLS_ENABLED=false`;
- default Edge1 Operator scopes include read scopes only and do not include
  `edge1.telephony.control.safe`.

Therefore merging this source does **not** by itself grant or activate host mutation.
The immutable Operations API runtime pinning flow also explicitly verifies the new
safe-control broker gate remains false when the runtime is installed.

Before production enablement, independently verify the service-control privilege
path available to the Operations API identity. Do not weaken `NoNewPrivileges`, run
the entire Operations API as root, enable the legacy global mutation switch, or add
a generic systemctl/sudo capability merely to make this action executable.

## Next increment

After source acceptance and live read-only deployment:

1. inspect the actual Edge1 privilege boundary for the fixed Telephony Console
   restart;
2. implement the narrowest dedicated privilege bridge if needed;
3. acceptance-test the complete control handshake with Asterisk and Messaging PIDs
   unchanged;
4. only then enable `telephony_safe_controls` and the corresponding Operator scope;
5. use the same pattern for Messaging pause/resume/verify controls rather than
   broadening this capability.
