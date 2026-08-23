# Edge1 Operator Controls v1 — disabled commissioning retry

## Verified live state after first commissioning attempt

- First disabled commissioning attempt reached broker installation and immutable Operations API pinning.
- Operator MCP pin/verification failed before acceptance.
- Transaction rollback restored the previous Operations API runtime and removed the privileged broker deployment.
- The failure was traced to `umask 077` worktree permissions: the Operations API runs as `wwadmin`, but the Operator MCP runs as the dedicated `edge1-operator` user.
- Retry hardening at PR #553 fixed Operator worktree read/traverse permissions, service-user import validation, process-environment pinning, and child-output visibility without enabling any write gate.

## Verified live state after second commissioning attempt

The retry at merge `05793dac4eedc51ce1c0fc628794fb2b5dc28b3b` advanced past the worktree preparation and reached the privileged broker installer. The installer enabled the broker service and then its immediate Unix-socket denial probe failed with `ConnectionRefusedError`.

Post-failure read-only inspection verified:

- primary checkout is clean `main` and has since advanced with unrelated reviewed work to `9518a7d969e5130766e5ea32615525f7e0500129`;
- no failed services are present;
- Operations API is healthy with 27 actions and `mutations_enabled=false`;
- Operator MCP is active on its prior read-only generation;
- `edge1-operator-privileged-broker.service` is active from the partial second attempt;
- no Telephony safe-control scope, Operations API safe gate, or approved Telephony runtime marker was activated by the commissioning workflow.

The active broker by itself is not host-write authority. The fixed peer/cgroup check, Operator write scope, Operations API safe-control gate, and approved Telephony runtime marker remain independent conditions.

## Second root cause: socket-path readiness race and incomplete installer rollback coverage

The broker process creates the Unix socket by bind/chown/chmod and only then calls `listen()`. The installer treated `-S /run/edge1-operator-privileged/control.sock` as readiness, so it could observe the pathname in the short interval before `listen()` completed. Its next immediate `connect()` then failed with `ECONNREFUSED`.

That denial probe was also outside the installer's explicit rollback branches. Because the script used `set -e`, the failed command substitution exited the installer before it printed its rollback path or invoked its own rollback. This explains why the broker remains active after the orchestrator rolled back the later-known control-plane paths.

Retry hardening now requires:

1. broker readiness to mean an actual successful Unix-socket connection that returns the exact expected `request_denied` response to a non-Operations peer;
2. repeated bounded connect/probe attempts rather than socket-path existence alone;
3. an armed `EXIT` rollback trap covering every post-install/post-activation failure path;
4. bounded service/journal/socket evidence capture before rollback;
5. an explicit broker service restart after switching the immutable `current` release, including when a broker was already active;
6. verification that the `current` symlink resolves to the reviewed release and the broker has a valid MainPID;
7. all write activation controls remain absent/off.

No PBX restart, Messaging restart, Telephony Console restart, tunnel restart, call, SMS/MMS, routing change, or Operator write activation is part of this hardening.
