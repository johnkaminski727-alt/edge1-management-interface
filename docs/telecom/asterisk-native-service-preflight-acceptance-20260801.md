# Asterisk Native-Service Migration Preflight Acceptance — 2026-08-01

## Authoritative evidence

Authenticated operator execution on `edge1.ww.cx` by `wwadmin` with bounded `sudo` elevation.

```text
/var/lib/wwcx-deployment-evidence/asterisk-native-service-preflight/20260801T031121Z/audit.txt
SHA-256: 001ab8350ca13d2ea5a8b972fee7aa29a66a03ad2c335f7956dd07c3c68531e5
```

The audit exited `0`, reported seven warnings and zero failures, and made no service, process, session, cgroup, boot, unit, configuration, listener, firewall, package, call, logger, module, container or traffic change.

## Accepted runtime state

Asterisk `22.10.1` was healthy with zero active channels, zero active calls and zero processed calls. The live PID was `1651722`, resolved from `/run/asterisk/asterisk.pid` rather than systemd.

The current generated compatibility unit is not supervising that process:

- `Type=forking`;
- `RemainAfterExit=yes`;
- `GuessMainPID=no`;
- `Restart=no`;
- `MainPID=0`;
- empty `ControlGroup`;
- `ActiveState=active`, `SubState=exited`;
- generated from `/etc/init.d/asterisk`.

The live process hierarchy is:

```text
systemd PID 1
└─ safe_asterisk PID 1651720
   └─ asterisk PID 1651722
```

The Asterisk process remains in `/user.slice/user-1000.slice/session-21312.scope`, not a system service cgroup.

## Legacy start contracts

`/etc/init.d/asterisk` starts `/usr/sbin/asterisk` directly with `start-stop-daemon`. It does not use `safe_asterisk` for the normal LSB start path.

The current live daemon was instead launched through `/usr/sbin/safe_asterisk`, whose own restart loop executes Asterisk in foreground mode. This runtime path therefore differs from the registered boot-time LSB contract.

A native systemd design should not stack systemd restart supervision around an unreviewed second restart supervisor. Direct foreground Asterisk ownership is the leading design, but it is not approved until FreePBX orchestration is attributed.

## FreePBX relationship

`freepbx.service` is a native enabled oneshot unit running `fwconsole start` and preserving its children in `/system.slice/freepbx.service`. Those children include PM2, the FastAGI Node service, the UCP Node service and a PHP event worker.

The unit declares ordering after MariaDB, Apache and network-online, but the captured unit metadata does not establish an explicit dependency on `asterisk.service`.

Before creating a native Asterisk unit, a further read-only audit must determine whether `fwconsole start`, `fwconsole stop`, or FreePBX source code independently starts, stops or restarts Asterisk. The future unit must avoid duplicate ownership and preserve supported FreePBX operations.

## Migration requirements

Any proposed native unit must:

- make systemd directly own the long-running Asterisk process;
- expose a correct nonzero `MainPID` and service `ControlGroup`;
- preserve the `asterisk:asterisk` identity and runtime paths;
- preserve safe start, stop and reload behavior;
- define the relationship with `freepbx.service` explicitly;
- avoid double restart supervision;
- include rollback to the existing SysV contract;
- be activated only in a controlled outage window;
- validate CLI health, process ownership, PID file, cgroup and every expected listener after start.

No unit installation, daemon reload, stop, start or restart is authorized by this acceptance record.
