# Edge1 Operator Completion Status

Last reconciled: 2026-08-18

## Purpose

Track the transition from repository architecture work to a permanently available, private, authenticated ChatGPT Edge1 operator without promoting repository state or historical deployment claims into live acceptance.

## Repository work completed

- Architecture definition.
- Authority and risk boundaries.
- Loopback HMAC/replay-protected Operations API and server-side allowlist.
- Fixed non-mutating Control Surfaces diagnostics.
- Read-only Control Surfaces live-inventory runner with safety-contract tests and CI.
- Named, parameterless MCP read-only tool contract.
- Fixed Operations API client restricted to loopback and a compile-time action set.
- Runtime mappings from named MCP tools to fixed read-only Operations API actions.
- `tools/list` / `tools/call` internal dispatch path.
- Removal of the legacy MCP-visible generic `edge1.exec` contract and generic `run_bounded(command)` scaffold.
- Authenticated loopback MCP Streamable HTTP transport.
- Source-side listener collision correction: the reviewed MCP transport is now assigned `127.0.0.1:8102`; established Portal API ownership of `127.0.0.1:8098` is preserved.
- Focused source validation for bounded-tool and deployment behavior.

## Repository implementation boundary

Source supports named read-only operator capabilities without accepting arbitrary commands, URLs, ports, paths, service names, action names, SQL, AMI/ARI commands, or caller-controlled shell parameters. The reviewed MCP HTTP transport requires bearer authentication and loopback binding.

Repository implementation is not equivalent to live deployment acceptance.

## Fresh live evidence — 2026-08-18T07:00Z

Fresh authenticated read-only Edge1 inspection established:

- live checkout: clean `main` at `ad0eed2dd0c52494c9805ce86739ccf2d4c40536`;
- `edge1-operator-mcp.service`: active/running, still executing `/usr/bin/python3 -m server.edge1_operator_entrypoint` rather than the reviewed HTTP transport;
- `wwcx-portal-api.service`: active/running and owns loopback `127.0.0.1:8098`;
- `/etc/edge1-operator/mcp-token`: absent, so the reviewed bearer-authenticated MCP HTTP transport is not live-installed;
- Operations API: healthy with 14 actions and `mutations_enabled: false`, demonstrating version/config drift from current source;
- BigBird: `0.3.4-alpha.2`, read-only, Library available with integrity `ok`;
- no public MCP management listener was created by this continuation pass.

Current repository source assigns MCP to loopback `8102`. Re-fetch `main` immediately before any deployment because concurrent repository work is active.

## Immediate operational dependency — Suricata

The larger checkout/MCP activation is intentionally deferred behind a live resource/sensor defect:

- `wwcx-network-sensor-suricata.service` is the intended managed libpcap sensor and is active/enabled;
- legacy `suricata.service` is disabled but active on the same `wg0` interface;
- the scheduled `wwcx-suricata-update.service` still declares a dependency on legacy `suricata.service` and its root-owned updater targets that legacy runtime;
- both packet engines experienced OOM/restart pressure during the 2026-08-18 rule-update window;
- latest captured state had about 348 MiB memory available and all 1 GiB swap in use;
- the updater failed during blocking rule reload when the legacy daemon was OOM-killed, then failed to reload the restored rules because its control socket was unavailable.

Do not run the existing runtime-consolidation script by itself: the current scheduled updater can recreate the retired legacy runtime.

## Remaining completion tasks

1. Capture the complete root-owned `/usr/local/sbin/wwcx-suricata-update` source read-only, plus the complete managed Suricata unit, without returning secret material.
2. Re-fetch current repository `main` and reconcile the scheduled updater to target only `wwcx-network-sensor-suricata.service` using the reviewed systemd reload/SIGUSR2 contract.
3. Add regression tests preventing any `suricata.service` dependency or target in the scheduled update path while preserving candidate validation, current-rules backup, rollback and restart-count verification semantics.
4. After green CI, perform one guarded live transaction with backups: install the reconciled updater/unit, daemon-reload if required, execute the reviewed runtime consolidation, and verify exactly one managed `--pcap=wg0` process, timer safety, observability and memory recovery. Roll back on failed verification.
5. Reassess RAM/swap before the larger Edge1 checkout/MCP activation.
6. Re-prove clean tree, ancestry and a current origin/main immediately before any checkout mutation; then create a host recovery point and fast-forward only if the safety gates still pass.
7. Install the reviewed MCP transport on loopback `8102`, provision its local token without returning the token to chat, and verify authentication rejection, initialization, ping, named tool discovery/calls, parameter rejection, audit output and restart persistence.
8. Run deterministic snapshot, drift, acceptance/evidence and Control Surfaces inventory on the reconciled host.
9. Complete the approved private MCP/Secure MCP Tunnel attachment only after local transport acceptance.

## Current execution-path status

The 1984 Hosting QEMU console is connected and visible through the browser connector, but the terminal canvas is not keyboard-controllable through that connector. No dedicated authenticated Edge1 live-shell connector is exposed in the present ChatGPT session. The attended `ssh edge1` relay therefore remains the current path for the one remaining read-only root source capture.

## Archive state

The operator workstream remains **active / incomplete**. Fresh live evidence now exists for the checkout, old operator unit, Portal listener, Operations API, BigBird and Suricata incident; production MCP transport installation, live convergence, acceptance and private ChatGPT attachment remain outstanding.

## Operating rule

Routine engineering and evidence work continues without repeated approval requests under the standing authorization. Credentials, secret material, irreversible/destructive changes, legal/commercial commitments, privileged network/security changes, and other explicit stop conditions remain gated.
