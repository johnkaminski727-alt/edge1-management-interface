# Ava Operator Parity — 2026-08-23

Objective: grant Ava access to the same authenticated Edge1 and Business159 operator services used by trusted WW.CX agents while preserving explicit approval gates.

Verified live prerequisites before implementation:
- Edge1 Agent Shell is active, full mode, root-backed, loopback `127.0.0.1:8114`, audited.
- `business159-secure-mcp-tunnel.service` is active under `business159-operator`.
- `edge1-agent-shell-secure-mcp-tunnel.service` is active.
- `wwcx-ava-office.service` is active on loopback `127.0.0.1:8116`.
- Business159 authenticated inspection verified host `business159.web-hosting.com`, principal `wwcxjywl`.

Policy implemented in `config/ava-operator-parity.json` and `server/ava_operator_policy.py`:
- reads: standing observe authority;
- reversible routine repair/filesystem operations: routine authority;
- deploy: confirmation required;
- raw Edge1/Business159 shell: attended confirmation required;
- credential/destructive/financial/legal/emergency classes: blocked.

Remaining wiring: Ava's browser worker/private AI gateway must consume typed operator capabilities through an internal broker. Do not expose generic command input to the browser or model-facing tool schema.

Live activation evidence:
- `wwcx-ava-operator-broker.service` enabled/active on `127.0.0.1:8118`; unauthenticated invoke returns 401.
- typed `edge1.read.health` completed through Edge1 Operator MCP.
- typed `business159.read.git` completed through authenticated `wwcxjywl` access.
- unconfirmed `edge1.shell.exec` denied with `confirmation_required`.
- Private AI gateway patched to `0.3.5-alpha.2`; typed operator read tools become available only with `operator:read`; routine action tools require separate `operator:actions:routine`.
- WW.CX PR #119 merged and deployed; authenticated admin AI requests now include `operator:read` only. No action/raw-shell scope is granted by the website.
