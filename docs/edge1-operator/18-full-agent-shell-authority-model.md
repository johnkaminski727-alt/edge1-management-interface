# Edge1 Full Agent Shell Authority Model

Last reconciled: 2026-08-23

## Decision

WW.CX now has two technically capable full-operator implementations plus the established bounded read-only Operator. They are assigned different operational roles so they do not become parallel authorities.

### 1. Ordinary Edge1 Operator — observation authority

`edge1-operator-mcp.service` at `127.0.0.1:8102/mcp` remains the routine production diagnostics surface. Its small named tool contract is preferred for health/status because it is predictable, low-noise, and easy to audit.

### 2. On-host Edge1 Agent Shell — canonical persistent mutation authority

`wwcx-edge1-agent-shell.service` at `127.0.0.1:8114/mcp` is the canonical persistent high-authority agent surface after live commissioning.

It is server-local, root-capable in `mode=full`, carried by the existing Secure MCP Tunnel `agent-shell` channel, and routed by the distinct `WW.CX Edge1 Agent Shell` workspace plugin. It provides arbitrary shell execution, typed filesystem read/write/update/management, and systemd control with a persistent on-host audit/runtime model.

After acceptance, normal trusted-agent mutation work should converge here.

### 3. SSH-backed Edge1 Live Shell — bootstrap/recovery/alternate transport

`tools/mcp/edge1-live-shell` is also intentionally capable when its environment gates and remote account permit it. Its role is bootstrap, recovery, and alternate transport from an authenticated connector host over OpenSSH.

Use it when:

- the on-host Agent Shell has not been installed yet;
- the Agent Shell/tunnel channel is unavailable and needs repair;
- an operator explicitly needs an independent SSH path for recovery/verification.

It must not become a second canonical deployment authority merely because it can perform the same Linux operations.

## Normal topology

```text
Trusted Agent / ChatGPT
        |
WW.CX Secure MCP Tunnel
        |
+--------------------------+
| 8102 read-only Operator  |  routine observation
| 8114 full Agent Shell    |  normal mutation authority
+--------------------------+
        |
      Edge1 OS
```

Recovery topology:

```text
Trusted Agent / ChatGPT
        |
authenticated connector host
        |
edge1-live-shell (SSH MCP)
        |
OpenSSH / existing trusted path
        |
      Edge1 OS
```

## Capability stance

The trusted on-host Agent Shell is deliberately full-capability. The private tunnel and bearer-protected MCP boundary are the normal connection/authentication boundary; the system should not re-create a per-command/per-file/per-service permission maze inside full mode.

The SSH recovery sidecar may retain deployment-time feature gates because it is useful in both reduced and full profiles. For the trusted full profile those gates may all be enabled, subject to the actual remote OS account/sudo authority.

Task-level authority still applies. Broad host capability does not automatically authorize separate external actions such as payments, contracts, public communications, emergency calling, number porting, or unrelated destructive changes.

## Current source state

- PR #535 introduced the persistent on-host Agent Shell and second Secure MCP Tunnel channel.
- PR #536 introduced the distinct Agent Shell workspace plugin/router and internal marketplace entry.
- subsequent main work expanded `edge1-live-shell` into a genuine full SSH operator as a complementary bootstrap/recovery path.

This source convergence does not itself prove live deployment.

## Commissioning order

1. Capture live Edge1 before-state through the existing read-only Operator.
2. If available, use the full SSH sidecar as the one-time bootstrap path; otherwise use another explicitly authenticated privileged Edge1 path.
3. Install `edge1-agent-shell.service` from current reviewed `main` using its dry-run-first installer.
4. Install/reload the reviewed Secure MCP Tunnel assets containing the `agent-shell` channel.
5. Verify 8114 is loopback-only and `/healthz` reports `mode=full`.
6. Verify the existing 8102 read-only Operator remains healthy.
7. From a fresh trusted agent session, prove all nine `edge1_agent_*` tools are discoverable.
8. Perform and roll back a harmless file update canary; verify the on-host JSONL audit record.
9. Use the canonical Agent Shell to perform the previously blocked durable Edge1 release-controller reconciliation.
10. Keep the SSH full shell available as recovery/alternate transport, not as a competing steady-state authority.

## Product-layer fallback

The preferred plugin binds to the existing Edge1 workspace app and expects the Secure MCP Tunnel to aggregate the second channel. If live discovery proves that the current app exposes only one channel, create a distinct workspace app for the Agent Shell and change only the plugin `.app.json` binding. Do not fake tool discovery or merge the high-authority tools into the bounded 8102 server simply to avoid creating the proper app binding.
