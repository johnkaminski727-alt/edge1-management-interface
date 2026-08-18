# Edge1 Operator Tool Contract

## Current MCP surface

The Edge1 Operator exposes a named, read-only MCP surface. The accepted contract is:

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

`edge1.snapshot` is an accepted part of the contract. It provides one deterministic read-only host snapshot through the audited Operations API.

The canonical static MCP declaration is `server/edge1_operator_mcp_protocol.py`. The registry derives from that declaration, and the MCP adapter must expose the same named surface. Tests should fail if these surfaces drift.

## Safety boundary

The MCP surface above is read-only. Generic shell execution and privileged mutation are not part of this contract. Controlled mutation, deployment, database recovery, and rollback remain separate Operations API actions governed by their own authorization and audit boundaries.

Operations must preserve the operator evidence model, including execution identity, verified host identity, timestamps, exit/result status, sanitized output, and durable evidence where applicable.

Secrets and private credentials are never returned through the tool surface.
