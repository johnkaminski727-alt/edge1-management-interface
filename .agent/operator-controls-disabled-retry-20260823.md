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

- no failed services were present;
- Operations API remained healthy with 27 actions and `mutations_enabled=false`;
- Operator MCP remained on its prior read-only generation;
- `edge1-operator-privileged-broker.service` remained active from the partial attempt because the installer failed before returning its rollback path;
- no Telephony safe-control scope, Operations API safe gate, or approved Telephony runtime marker was activated by the commissioning workflow.

PR #556 / merge `99a65db2a62b93339fd53ed1d49b0f77a8dd986c` fixed the broker readiness race by requiring a successful denial response rather than socket-path existence and armed an installer-wide rollback trap for post-activation failures.

## Verified live state after third commissioning attempt

The next attended attempt ran against reviewed commit `1c5eab5aef4046d445347370e491b038208073e8`.

Observed sequence:

1. exact reviewed main fast-forwarded cleanly;
2. immutable Operations API and Operator worktrees were prepared;
3. privileged broker installation accepted;
4. immutable Operations API runtime accepted;
5. Operator MCP restart reached loopback readiness, but postcondition verification failed with `service working directory does not match immutable runtime`;
6. Operator MCP rollback completed and listened again;
7. commissioning rollback restored the Operations API runtime and privileged broker.

No write authority was activated and no Asterisk, Messaging Gateway, Telephony Console, Secure MCP Tunnel, call, SMS/MMS, or routing mutation was part of the attempt.

## Third root cause: runtime cwd must not depend only on systemd WorkingDirectory merge order

`server/edge1_operator_http.py` does not call `chdir()`, so the runtime CWD mismatch is outside application behavior. The immutable pin previously supplied both a systemd `WorkingDirectory=$RUNTIME` and a module-mode Python `ExecStart`. A pre-existing or later systemd drop-in can still determine the effective `WorkingDirectory` property, while the service may become healthy enough to answer HTTP before the postcondition notices that mismatch.

The hardened pin now makes the reviewed `ExecStart` itself enforce the process cwd with:

`/usr/bin/env --chdir=$RUNTIME ... /usr/bin/python3 -m server.edge1_operator_http ...`

This makes the Python import root and process cwd an execution property of the reviewed immutable command rather than relying solely on unit/drop-in merge order. The systemd `WorkingDirectory=$RUNTIME` setting remains as defense in depth.

Additional hardening:

- preflight proves `/usr/bin/env` supports `--chdir` before service mutation;
- accepted state still requires `/proc/<pid>/cwd` to equal the exact immutable runtime;
- effective capability manifest and read-only scope values are still verified from `/proc/<pid>/environ`;
- failure evidence now records the observed process cwd when available;
- no Telephony write scope, Operations API safe-control gate, approved Telephony runtime marker, legacy mutation gate, PBX restart, Messaging restart, Telephony Console restart, tunnel restart, call, SMS/MMS, or routing change is enabled by this hardening.

## Repeated exact-main guard stops

After the CWD hardening merged, subsequent attended commands correctly stopped before mutation whenever `origin/main` advanced between review and execution. The observed intervening commits were Ava Office / Number Portability read-only runtime work and did not alter Operator-control paths. The exact equality guard was safe but forced repeated manual commit chasing.

The commissioning wrapper is therefore being extended with a `--reviewed-control-base` mode. In this mode it:

1. fetches current `origin/main`;
2. requires the reviewed base to be an ancestor of current `origin/main`;
3. compares a fixed fail-closed set of Operator, Operations API, broker, Telephony-control, validation, and deployment paths between the reviewed base and current `origin/main`;
4. refuses commissioning and requires fresh review if any protected control-plane path changed;
5. otherwise resolves the current `origin/main` as the deploy commit and proceeds with the same immutable runtime, rollback, read-only scope, safe-gate-off, and protected-service PID invariants.

This removes unrelated-main race churn without weakening the control-plane review boundary. Exact `--expected-commit` mode remains available and unchanged.
