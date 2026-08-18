# Edge1 Operator Tool Contract

## Current MCP surface

The Edge1 Operator exposes a named MCP surface. Sixteen tools are read-only;
one tool (`agent.turn.handoff`) is a bounded, parameterized write. The
accepted contract is:

Read-only:

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
- `agent.turn.status` -- reads authoritative turn-ownership state for a
  (`task_id`, `conversation_id`) pair. Parameterized (both fields required),
  unlike the sixteen zero-argument tools above.

Bounded write:

- `agent.turn.handoff` -- explicitly transfers turn ownership for a
  (`task_id`, `conversation_id`) pair. Requires the current owner
  (`requesting_agent` must match the stored owner), the current expected
  `turn_epoch`, and an `idempotency_key`. A stale epoch or an unauthorized
  requester is rejected without mutating state. A repeated request with the
  same `idempotency_key` and identical parameters replays the prior result
  safely rather than double-applying; the same key reused with different
  parameters is rejected as a conflict rather than silently returning a
  stale cached result. This does not create tasks/conversations -- state
  must already exist (see `server/edge1_operator_turn_state.py`) -- and it
  does not invoke BigBird or perform automatic timeout-based transfer.

`edge1.snapshot` is an accepted part of the contract. It provides one
deterministic read-only host snapshot through the audited Operations API.

The canonical static MCP declaration is `server/edge1_operator_mcp_protocol.py`.
The registry derives from that declaration (including each tool's `access`
level), and the MCP adapter must expose the same named surface. Tests should
fail if these surfaces drift.

## Turn-ownership storage

`agent.turn.status` and `agent.turn.handoff` are backed by
`server/edge1_operator_turn_state.py`, a SQLite database (Python stdlib
`sqlite3`, no external dependency) local to the operator process, not a
shared network database and not the live Edge1 host state itself.

Four tables in one database commit atomically for every handoff: `turn_state`
(current ownership/epoch), `turn_audit` (append-only handoff audit trail),
`turn_outbox` (durable event record for future consumers), and
`turn_idempotency` (replay/conflict detection). A handoff writes to all four
in a single SQLite transaction (`BEGIN IMMEDIATE` ... `COMMIT`) -- a real
atomic multi-table commit, verified by a forced-rollback test that confirms
zero partial rows survive a mid-transaction failure.

The legacy `edge1_operator_audit` JSONL module is retained only as an
optional, non-authoritative post-commit projection. Its failure does not
roll back or otherwise affect the already-committed SQLite transaction, and
it is not required for correctness.

## Safety boundary

The bulk of the MCP surface is read-only. The one write tool,
`agent.turn.handoff`, is narrowly scoped to in-repo coordination state (a
local SQLite database, not the live host, not a shared/external database)
and cannot be used to execute commands, change host configuration, or reach
outside its own turn-ownership record. Generic shell execution and
privileged host mutation are not part of this contract. Controlled mutation
of Edge1 itself, deployment, database recovery, and rollback remain separate
Operations API actions governed by their own authorization and audit
boundaries.

Operations must preserve the operator evidence model, including execution
identity, verified host identity, timestamps, exit/result status, sanitized
output, and durable evidence where applicable. `agent.turn.handoff` records a
`turn.handed_off` event in the `turn_audit` table as part of the same atomic
transaction as the state change; the legacy JSONL audit module records an
additional, non-authoritative projection of the same event afterward.

Secrets and private credentials are never returned through the tool surface.
