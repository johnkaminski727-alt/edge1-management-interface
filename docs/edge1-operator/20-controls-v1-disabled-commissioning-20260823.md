# Edge1 Operator Controls v1 — disabled commissioning — 2026-08-23

## Purpose

Commission the new Operator control-plane code and privilege boundary on Edge1 while
keeping host-write authority unavailable to the connected Operator.

This phase is intentionally **not** control activation. It establishes reviewed,
immutable runtimes and the fixed privileged broker so the next activation decision
has a small, measurable boundary.

## Pre-commissioning live findings

Read-only live inspection showed:

- the public Edge1 Operator was still running the previously accepted immutable
  generation rather than the newly merged control-plane source;
- the Operations API was healthy and loopback-only with legacy mutations disabled;
- the shared `/opt/edge1-management-interface` checkout was on `main` but behind
  `origin/main`;
- Asterisk, Messaging Gateway and the Telephony Console were active;
- `asterisk.service` is SysV-generated on this host and reports `MainPID=0` even
  though the Asterisk process and fixed native diagnostics are healthy.

The `MainPID=0` detail means a direct `systemctl show ... MainPID` dependency guard is
not a valid Asterisk process-identity test on Edge1.

## Asterisk process identity correction

`server/asterisk_process_identity.py` now resolves one validated Asterisk process by
this fixed hierarchy:

1. a non-zero systemd `MainPID` whose `/proc/<pid>/comm` is exactly `asterisk`;
2. `/run/asterisk/asterisk.pid` or `/var/run/asterisk/asterisk.pid`, again validated
   against `/proc/<pid>/comm`;
3. exactly one validated Asterisk process whose argv contains `-f`.

Failure to resolve exactly one trusted process fails closed. No PID is accepted merely
because a numeric value was supplied by a caller.

Both the unprivileged Operations API handler and the fixed root broker use this
resolver for before/after Asterisk process continuity checks. The root broker release
contains a root-owned immutable copy of the helper beside the broker code.

## Disabled commissioning transaction

`deploy/edge1-operator/commission-controls-v1-disabled.sh` is the one-shot attended
commissioning entrypoint. It requires:

- authenticated `wwadmin` execution on `edge1.ww.cx`;
- clean primary checkout on `main`;
- exact reviewed `origin/main` commit;
- no pre-existing Telephony approved-runtime marker.

The transaction then:

1. creates a safety branch before fast-forwarding the shared checkout when needed;
2. prepares detached clean immutable worktrees for the Operations API and Operator
   MCP at the exact reviewed commit;
3. grants only the dedicated `edge1-operator` group read/traverse access to the
   Operator worktree and verifies the service identity can import it without writing;
4. records Asterisk, Messaging Gateway, Telephony Console and Secure MCP Tunnel
   process identities;
5. installs the fixed root broker from a root-owned immutable release;
6. repins the Operations API to the reviewed immutable worktree with
   `EDGE1_OPS_TELEPHONY_SAFE_CONTROLS_ENABLED=false`;
7. pins the Operator MCP itself to a separate reviewed immutable worktree with only
   the explicit read scopes `edge1.status.read`, `edge1.telephony.read`, and
   `edge1.messaging.read`;
8. validates the local MCP tool surface and capability summary;
9. calls the published `edge1.telephony_console_reload` tool and requires it to be
   rejected as `capability_denied` before any root-broker `authorized_attempt` is
   recorded;
10. verifies Asterisk, Messaging Gateway, Telephony Console and Secure MCP Tunnel
    process identities did not change.

Each runtime/broker deployment step creates protected evidence and a rollback script.
The orchestrator invokes available rollback paths if a later commissioning gate fails.
Child deployment output is streamed through `tee` so a failed sub-step is visible to
the attended operator instead of disappearing inside command substitution.

## First live attempt and rollback

The first live disabled-commissioning attempt at merge
`e2ec00276f617b4a4cb19a4dac41aa49f577dcb7` established the following boundary:

- fixed privileged broker installation succeeded;
- immutable Operations API pinning succeeded;
- immutable Operator MCP pin/verification failed before acceptance;
- the orchestrator rolled the Operations API and broker back;
- the post-rollback host had no failed services, the Operations API was healthy with
  27 actions and mutations disabled, and the existing Operator returned to its prior
  read-only surface.

The failure boundary exposed a deterministic permissions defect in the commissioning
wrapper. The wrapper intentionally starts with `umask 077` and creates detached Git
worktrees as `wwadmin`. That makes a fresh worktree private to `wwadmin`. The
Operations API runs as `wwadmin`, so its immutable runtime was usable and accepted.
The Operator MCP runs as the dedicated `edge1-operator` identity, so the same private
worktree could not be relied upon as a readable/traversable service runtime.

The retry hardening therefore explicitly changes only the Operator worktree group to
`edge1-operator`, grants that group read/traverse (`g+rX`), strips all permissions for
other users, and verifies required source files plus a no-bytecode import as the
service identity before any control-plane deployment begins. No group write bit is
granted.

The retry also removes capability-policy dependence on systemd environment-file
precedence. The immutable Operator pin places the fixed capability manifest path and
fixed read-only scope set directly in the `ExecStart` process environment using
`/usr/bin/env`, then verifies the actual `/proc/<pid>/environ` values. Failure paths
record only bounded service properties and recent service journal evidence before
rolling back.

## Authority state after successful commissioning

Expected accepted state:

- fixed privileged broker: installed and active;
- broker listener: local Unix socket only;
- Operations API: immutable reviewed runtime, loopback HTTP only;
- legacy Operations API mutations: disabled;
- `telephony_safe_controls` Operations API gate: disabled;
- Operator MCP: immutable reviewed runtime, loopback only;
- public write tool: published but denied by missing write scope;
- `edge1.telephony.control.safe` scope: absent;
- root-owned Telephony approved-runtime marker: absent;
- Asterisk restart: no;
- Messaging Gateway restart: no;
- Telephony Console restart: no;
- Secure MCP Tunnel restart: no;
- call/SMS/MMS traffic generated: no.

The broker being installed is therefore **not** sufficient authority to perform the
host mutation. The Operator scope, Operations API safe-control gate, and approved
Telephony runtime marker are all independent later activation conditions.

## Why the Operator MCP is also immutable

Before this increment, the Operations API could be pinned to an immutable worktree
while the MCP process itself still executed from the shared engineering checkout.
That is acceptable for a read-only tool surface but not the desired boundary for a
future host-write capability.

`deploy/pin-edge1-operator-mcp-runtime.sh` therefore pins the Operator MCP to its own
detached worktree and explicitly supplies the read-only scope set. Updating the
shared checkout after commissioning does not silently alter the running Operator
code generation.

## Activation is a separate phase

Disabled commissioning does not create
`/etc/wwcx-edge1-operator/telephony-console-control.json`, does not enable
`EDGE1_OPS_TELEPHONY_SAFE_CONTROLS_ENABLED`, and does not add
`edge1.telephony.control.safe` to the Operator scopes.

The first live agent-controlled Telephony Console reload must be handled as a separate
activation/acceptance operation after disabled commissioning is verified.
