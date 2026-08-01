# Asterisk Service Lifecycle Audit Acceptance — 2026-08-01

## Authoritative evidence

Authenticated operator execution on `edge1.ww.cx` by `wwadmin` with bounded `sudo` elevation.

```text
/var/lib/wwcx-deployment-evidence/asterisk-service-lifecycle/20260801T025832Z/audit.txt
SHA-256: 1c7b6e92cba386a0599a0fbc937b24087d4e4bf4e118dfc7704271e6def1b2bd
```

The audit exited `0`, reported four warnings and zero failures, and made no service, process, session, cgroup, boot, configuration, listener, firewall, package, call, logger, module, container, or traffic change.

## Accepted runtime facts

Asterisk `22.10.1` was healthy and idle:

- zero active channels;
- zero active calls;
- zero processed calls;
- live PID `1651722` from `/run/asterisk/asterisk.pid`;
- process command `/usr/sbin/asterisk -f -U asterisk -G asterisk -vvvg -c`;
- parent `/usr/sbin/safe_asterisk -U asterisk -G asterisk` with parent PID `1`.

The live Asterisk process started on `2026-07-31 23:37:59 UTC`.

## Generated SysV unit state

`asterisk.service` is not a native systemd unit. It was generated from `/etc/init.d/asterisk` by `systemd-sysv-generator`:

```text
FragmentPath=/run/systemd/generator.late/asterisk.service
SourcePath=/etc/init.d/asterisk
Type=forking
RemainAfterExit=yes
GuessMainPID=no
MainPID=0
ControlGroup=
ActiveState=active
SubState=exited
Restart=no
```

The generated unit reports active since `2026-07-20 03:40:55 UTC`, more than eleven days before the currently running Asterisk process started. Therefore the generated unit's active state does not identify or supervise the current daemon.

## Process and session ownership

The live process is attached to:

```text
/user.slice/user-1000.slice/session-21312.scope
```

Session `21312` belongs to `wwadmin`, was created by `sshd`, and was observed in `closing` state with an `abandoned` scope. The live Asterisk process and its `safe_asterisk` parent remained in that session cgroup even though `safe_asterisk` had been re-parented to PID `1`.

This establishes that the current daemon was launched through a login-session context rather than a system service cgroup.

## Boot registration

Traditional SysV boot links are present:

- start links in runlevels `2`, `3`, `4`, and `5`;
- stop links in runlevels `0`, `1`, and `6`.

The init script is:

```text
/etc/init.d/asterisk
SHA-256: 2597341fc6f136fecf7e239bb00e3c0e2dc3ced7beffdf7a2e6caf8ae18db1b0
```

Boot registration exists, but this does not prove that the present manually/session-launched daemon will survive session cleanup or that a future boot will produce a correctly supervised process.

## Operational classification

The accepted classification is:

> Asterisk is healthy but not presently supervised as a native systemd service. The generated SysV compatibility unit is active-exited, has no MainPID or ControlGroup, and does not own the live session-scoped daemon.

Consequences:

- systemd cannot monitor the live process for exit or crash;
- `Restart=no` provides no systemd recovery;
- service status can remain `active (exited)` while the daemon is absent or replaced;
- logout/session cleanup semantics are uncertain;
- restart and stop behavior may depend entirely on the init script and PID file;
- reboot registration exists but reboot recovery has not been proven.

## Decision boundary

Accepted:

- preserve the evidence and SHA-256 above;
- treat the service/runtime ownership mismatch as material;
- avoid relying on `systemctl is-active asterisk` as a daemon-health check;
- require CLI health, PID validation, and listener checks for current verification;
- perform a read-only migration preflight before designing a native unit.

Not authorized or performed:

- service stop, restart, reload, or reboot;
- session termination or cgroup migration;
- native-unit installation or SysV-link removal;
- FreePBX configuration changes;
- listener, firewall, call, CAP-feed, or production-traffic activation.
