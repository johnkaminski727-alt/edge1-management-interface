# Edge1 Operator Completion Status

Last reconciled: 2026-08-18

## Purpose

Track the transition from repository architecture work to a permanently available, private, authenticated ChatGPT Edge1 operator without confusing repository completion with live acceptance.

## Repository work completed

- Loopback HMAC/replay-protected Operations API with a fixed server-side allowlist.
- Named, parameterless MCP read-only tool contract and bounded runtime mappings.
- Removal of the legacy MCP-visible generic `edge1.exec` / generic command scaffold.
- Authenticated loopback MCP HTTP transport with fail-closed token/origin handling.
- Source-side listener correction: Portal API remains on `127.0.0.1:8098`; reviewed MCP transport is on `127.0.0.1:8102`.
- Deterministic snapshot, drift, acceptance/evidence, Control Surfaces inventory, and reviewed safe-change foundations.
- PR #388 repository-owned Suricata updater/runtime repair, including guarded backup/verify/rollback deployment and regression tests.

## Fresh live evidence — 2026-08-18T07:00Z

Authenticated read-only Edge1 inspection established:

- live checkout: clean `main` at `ad0eed2dd0c52494c9805ce86739ccf2d4c40536`;
- `edge1-operator-mcp.service`: active/running but still executing `/usr/bin/python3 -m server.edge1_operator_entrypoint`, not the reviewed HTTP transport;
- `wwcx-portal-api.service`: active/running and owns loopback `127.0.0.1:8098`;
- `/etc/edge1-operator/mcp-token`: absent;
- Operations API: healthy with 14 actions and `mutations_enabled: false`, showing version/config drift from current source;
- BigBird: `0.3.4-alpha.2`, read-only, Library available, integrity `ok`;
- two Suricata runtimes simultaneously active on `wg0`, with about 2.3 GiB RSS combined and all 1 GiB swap consumed at the latest capture.

The legacy `suricata.service` is disabled but active because the live scheduled updater still requires and targets it. The 2026-08-18 update window produced repeated OOM kills and a failed blocking reload/restore transaction.

## Current reviewed repair path

PR #388 merged as `41c8c2eb824e8ae51afaa60afcef563c1b11ebb3` after Edge1 Operator Validation and Validate repository passed.

The repair intentionally avoids a bulk production-checkout fast-forward. Its documented path is:

1. fetch the merged repair commit;
2. create a detached temporary worktree pinned to that exact commit;
3. run `deploy/repair-edge1-suricata-update-runtime.sh` as root with `EXPECTED_COMMIT` pinned;
4. let the script capture pre-state and backups, install only the updater/service/timer artifacts, daemon-reload, retire the duplicate legacy runtime, and verify exactly one managed `--pcap=wg0` sensor;
5. preserve transaction evidence and automatically restore prior updater/unit files plus the prior legacy-service state on failed verification;
6. reassess memory/swap and only then resume broader checkout/MCP activation.

The repair does not change firewall, DNS, WireGuard, routing, certificates, authentication, packet-filter policy, or production traffic.

## Remaining completion tasks

- Execute and accept the merged PR #388 guarded Suricata repair on Edge1.
- Verify single-runtime state, timer dependency, observability, memory/swap recovery, and rollback evidence.
- Re-fetch current `main`, re-prove clean-tree/ancestry state, create a fresh host recovery point, and separately reconcile the materially old live checkout.
- Install the reviewed MCP transport on loopback `8102` and provision its local token without returning secret material to chat.
- Prove unauthenticated/invalid-auth rejection, initialization, ping, named tool discovery/calls, parameter rejection, audit output and restart persistence.
- Run deterministic snapshot, drift, acceptance/evidence and Control Surfaces inventory on the reconciled host.
- Complete the approved private MCP/Secure MCP Tunnel attachment only after local transport acceptance.

## Current execution-path status

The 1984 Hosting QEMU console is connected and visible through the browser connector, but its terminal canvas is not keyboard-controllable through that connector. No dedicated authenticated Edge1 live-shell connector is exposed in this ChatGPT session. Attended `ssh edge1` therefore remains the current path for the guarded live transaction.

## Archive state

The operator workstream remains **active / incomplete**. Fresh live evidence exists and the immediate Suricata source repair is merged, but the live repair, production checkout convergence, MCP 8102 installation/acceptance, snapshots/drift and private ChatGPT attachment are still outstanding.

## Operating rule

Routine engineering and evidence work continues without repeated approval requests under the standing authorization. Credentials, secret material, irreversible/destructive changes, legal/commercial commitments, privileged network/security changes, and other explicit stop conditions remain gated.
