# Asterisk Native systemd Integration Design — Draft, 2026-08-01

## Status

Design-only. Not approved for installation or activation.

## Problem

The live Asterisk daemon is healthy but is not supervised by `asterisk.service`. It was started through `safe_asterisk` from an SSH session and remains in a user-session cgroup.

The installed FreePBX lifecycle commands directly launch and terminate `safe_asterisk`. A native systemd service cannot safely take ownership while those commands retain independent control.

## Rejected designs

### Keep the generated SysV compatibility unit

Rejected as the target state because it reports `active (exited)`, has `MainPID=0`, has no service cgroup and uses `Restart=no`.

### Put `safe_asterisk` behind systemd unchanged

Rejected as the preferred design because it retains two restart supervisors and preserves ambiguous PID ownership. The current `safe_asterisk` script backgrounds its restart loop, which also weakens direct systemd process supervision.

### Edit installed FreePBX PHP source in place

Rejected because package or module upgrades could overwrite the changes and because lifecycle ownership would depend on an unsupported local patch.

### Install a direct foreground Asterisk unit without changing FreePBX orchestration

Rejected because `fwconsole start` could launch a second supervisor and `fwconsole stop` could terminate the native unit's process outside the unit contract.

## Preferred architecture

The target architecture should have these boundaries:

- `asterisk.service` owns `/usr/sbin/asterisk -f -U asterisk -G asterisk` directly;
- systemd provides the only automatic restart policy;
- `freepbx.service` owns FreePBX's PM2, PHP and Node children;
- FreePBX configuration generation remains supported;
- FreePBX lifecycle commands delegate Asterisk start and stop to systemd through an update-resilient mechanism;
- reload behavior uses a bounded Asterisk CLI or native unit reload action;
- `safe_asterisk` is not active after migration.

## Candidate integration mechanisms to evaluate offline

1. A supported FreePBX configuration option or service-manager integration that delegates Asterisk lifecycle to systemd.
2. A packaged wrapper or command-path override outside module source that FreePBX recognizes and that delegates to `systemctl`.
3. A FreePBX service override that separates Asterisk lifecycle from `fwconsole start/stop`, provided PM2 and other FreePBX children remain correctly managed.
4. A locally packaged, version-tracked integration patch only if no supported boundary exists; this is the least preferred option and must include update detection.

## Candidate native unit properties

A future candidate should be tested offline with properties equivalent to:

```ini
[Unit]
Description=Asterisk PBX
Wants=network-online.target
After=network-online.target mariadb.service
Before=freepbx.service wwcx-telephony-console.service

[Service]
Type=simple
User=asterisk
Group=asterisk
RuntimeDirectory=asterisk
RuntimeDirectoryMode=0755
ExecStart=/usr/sbin/asterisk -f -U asterisk -G asterisk
ExecReload=/usr/sbin/asterisk -rx 'core reload'
Restart=on-failure
RestartSec=5s
TimeoutStopSec=120s
KillMode=mixed

[Install]
WantedBy=multi-user.target
```

This is an illustrative starting point, not an approved production unit. Exact arguments, stop semantics, runtime-directory ownership, reload behavior and FreePBX ordering must be validated.

## Required offline tests

- Asterisk starts with the production configuration and creates the expected PID file.
- `MainPID` is the live Asterisk process.
- The daemon and every child remain inside the service cgroup.
- A clean stop does not leave `safe_asterisk` or Asterisk processes behind.
- A forced Asterisk failure triggers exactly one restart.
- `fwconsole reload` continues to generate and apply configuration safely.
- `fwconsole start`, `stop` and `restart` cannot create a duplicate daemon or bypass systemd.
- FreePBX PM2, FastAGI, UCP and PHP workers remain healthy.
- Expected listeners and firewall behavior remain unchanged.
- Rollback to the current SysV/FreePBX contract is tested.

## Production gate

Production activation is conditional work requiring a controlled outage, an exact rollback procedure, pre-change evidence, post-start functional checks and operator authorization at execution time.
