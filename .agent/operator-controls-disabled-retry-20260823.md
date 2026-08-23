# Edge1 Operator Controls v1 — disabled commissioning retry

## Verified live state after first commissioning attempt

- First disabled commissioning attempt reached broker installation and immutable Operations API pinning.
- Operator MCP pin/verification failed before acceptance.
- Transaction rollback restored the previous Operations API runtime and removed the privileged broker deployment.
- Primary checkout remains clean `main` at `e2ec00276f617b4a4cb19a4dac41aa49f577dcb7`.
- Live Operations API is healthy with 27 actions and `mutations_enabled=false`.
- Existing Operator MCP is active on the prior read-only surface.
- No failed services were observed after rollback.
- Asterisk remains SysV-generated with systemd `MainPID=0` and is handled by the fixed process-identity resolver.

## Root deployment weakness to correct before retry

The immutable Operator MCP pin currently injects `EDGE1_OPERATOR_CAPABILITIES` and `EDGE1_OPERATOR_SCOPES` with systemd `Environment=` while the base unit also loads `/etc/edge1-operator/edge1-operator.env` through `EnvironmentFile=`. Capability-critical policy must not depend on external environment-file precedence.

Retry hardening will:

1. put the fixed capability manifest path and fixed read-only scope set directly in the `ExecStart` process environment through `/usr/bin/env`, after all systemd-provided environment sources;
2. verify the effective process environment through `/proc/<pid>/environ` rather than only `systemctl show -p Environment`;
3. capture safe status/journal evidence on Operator pin failure;
4. preserve child deployment output instead of hiding it inside command substitution;
5. prevent duplicate rollback traps from inherited ERR handling;
6. keep the safe-control scope, Operations API safe-control gate and approved-runtime marker absent/off.

No write activation, PBX restart, Messaging restart, Telephony Console restart, tunnel restart, call, SMS/MMS or routing change is part of this retry hardening.
