# FreePBX–Asterisk Orchestration Acceptance — 2026-08-01

## Authoritative evidence

Authenticated operator execution on `edge1.ww.cx` by `wwadmin` with bounded `sudo` elevation.

```text
/var/lib/wwcx-deployment-evidence/freepbx-asterisk-orchestration/20260801T031720Z/audit.txt
SHA-256: 184bb959a766ec5cda85a2caa2d8cb26dcd126428b201bf6b396d29c5b4dd7f4
```

The audit exited `0`, reported four warnings and zero failures, and made no service, process, PM2, session, cgroup, boot, unit, configuration, listener, firewall, package, call, database, logger, module, container or traffic change.

## Accepted runtime state

Asterisk `22.10.1` was healthy with zero active channels, zero active calls and zero processed calls. PID `1651722` was resolved from `/run/asterisk/asterisk.pid`, not from systemd.

The live hierarchy remained:

```text
systemd PID 1
└─ safe_asterisk PID 1651720
   └─ asterisk PID 1651722
```

The Asterisk process remained attached to `/user.slice/user-1000.slice/session-21312.scope`.

The generated `asterisk.service` compatibility unit remained `active (exited)` with `MainPID=0`, no `ControlGroup`, `Restart=no`, and no ownership of the live process.

## FreePBX orchestration finding

FreePBX directly controls the Asterisk lifecycle.

The installed FreePBX source shows:

- `fwconsole start` calls `Start.class.php::startAsterisk()`;
- that method launches `/usr/bin/env safe_asterisk -U <user> -G <group> ... &`;
- `fwconsole stop` calls `Stop.class.php::stopAsterisk()`;
- the stop path explicitly runs `killall safe_asterisk` and then performs Asterisk shutdown logic;
- `fwconsole reload` contains Asterisk reload and reload-skip handling.

Therefore, FreePBX is not merely ordered around Asterisk. It is an active lifecycle controller for the current `safe_asterisk` process.

## Service ownership consequence

A native systemd unit that directly launches foreground Asterisk would conflict with the installed FreePBX control path unless FreePBX orchestration is deliberately redirected.

Without that integration:

- `fwconsole start` could launch a second `safe_asterisk` supervisor outside the native unit;
- `fwconsole stop` could kill the process that systemd expects to own;
- systemd restart policy and FreePBX restart behavior could race;
- PID, cgroup and service state could diverge again;
- package updates could overwrite ad-hoc edits to FreePBX source.

A native unit must not be installed while `fwconsole start/stop` independently starts and stops Asterisk through `safe_asterisk`.

## FreePBX service boundary

`freepbx.service` is an enabled oneshot unit using:

```text
ExecStart=/usr/sbin/fwconsole start
ExecStop=/usr/sbin/fwconsole stop
```

Its service cgroup contains PM2, the call-transfer PHP worker, FastAGI Node service and UCP Node service. Asterisk is not inside that cgroup.

No explicit captured dependency or ordering relationship exists between `freepbx.service` and `asterisk.service`.

## Accepted design direction

The preferred long-term direction remains one supervisor and one ownership model:

1. systemd directly owns foreground Asterisk;
2. systemd exposes a nonzero `MainPID` and a dedicated service cgroup;
3. systemd provides restart-on-failure behavior;
4. FreePBX retains responsibility for configuration generation, reload requests and its PM2/PHP/Node children;
5. FreePBX start/stop behavior must be integrated with the native unit through a supported or update-resilient boundary rather than source-file edits;
6. `safe_asterisk` must not remain as a second restart supervisor after migration.

This direction is not yet approved for deployment. The exact integration mechanism must be designed and tested offline before a controlled outage.

## Deployment gates

Before activation, the implementation must provide:

- an update-resilient FreePBX-to-systemd integration mechanism;
- explicit ordering between Asterisk, MariaDB, network-online and FreePBX;
- a rollback path restoring the generated SysV contract and current FreePBX behavior;
- a controlled outage window;
- verification of CLI health, PID file, cgroup, listeners, FreePBX UI, PM2 children and configuration reload behavior;
- proof that `fwconsole start`, `stop`, `restart` and `reload` cannot create duplicate ownership.

No native unit, drop-in, wrapper, source modification, daemon reload, stop, start or restart is authorized by this acceptance record.
