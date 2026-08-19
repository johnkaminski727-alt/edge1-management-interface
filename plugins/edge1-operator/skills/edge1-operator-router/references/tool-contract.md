# Edge1 Operator live tool contract

The live Edge1 Operator exposes exactly these bounded tools:

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

No arbitrary remote-shell tool belongs in this contract.

Acceptance behavior:

1. A direct request for Edge1 identity calls `edge1.identity` live.
2. A natural-language request for current Edge1 health calls `edge1.health` live.
3. Automatic invocation must not depend on the user manually selecting the app or @mentioning it.
4. Never claim a live pass if the dependency/tool was not actually invoked.
