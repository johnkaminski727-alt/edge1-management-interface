# Asterisk High UDP Attribution Failed Run — 2026-08-01

## Evidence

Authenticated operator execution on `edge1.ww.cx` by `wwadmin` with bounded `sudo` elevation.

```text
/var/lib/wwcx-deployment-evidence/asterisk-high-udp-attribution/20260801T023526Z/audit.txt
SHA-256: 03d720b84737647c851ed4c2dbbb5c8005bfc072e26271429ebf8f7681153867
```

The audit exited `1`, reported one warning and one failure, and made no tracer, packet-capture, configuration, service, listener, route, certificate, firewall, package, call, logger, container, or traffic change.

## Failure classification

The failure was diagnostic rather than operational:

```text
FAIL: Unable to resolve Asterisk MainPID
```

Asterisk itself remained active and healthy. The service is SysV-backed under systemd compatibility, and `systemctl show -p MainPID --value asterisk` did not return a usable PID even though the live Asterisk process and sockets remained present.

Because PID discovery failed, the audit intentionally skipped:

- Asterisk-specific `ss` filtering;
- high-port extraction and classification;
- `/proc/<pid>/fd` socket-inode mapping;
- Asterisk network-namespace metadata.

The evidence must therefore not be treated as a completed attribution result.

## Valid partial findings

The non-PID-dependent checks established:

- configured Asterisk RTP range: UDP `10000-20000`;
- kernel ephemeral range: UDP/TCP `32768-60999`;
- observed high ports `55539` and `59177` fall inside the kernel ephemeral range and outside the configured RTP range;
- zero active channels, zero active calls and zero processed calls;
- `res_rtp_asterisk` was loaded with use count `0`;
- ICE support was enabled in the RTP stack;
- STUN was disabled in the RTP runtime settings;
- `res_stun_monitor` was loaded with use count `0`;
- `res_resolver_unbound` was loaded with use count `1`;
- the existing duplicate PJSIP transport defect remained unchanged.

These observations make persistent resolver or other control-plane ephemeral sockets more plausible than active RTP media sockets, but they do not prove module ownership.

## Correction

The follow-up audit now resolves and validates the Asterisk PID through this guarded order:

1. systemd `MainPID`;
2. `/run/asterisk/asterisk.pid` or `/var/run/asterisk/asterisk.pid`;
3. one uniquely matched live `asterisk -f` process from the process table.

Every candidate must be numeric, live under `/proc`, and have process name `asterisk`. Ambiguous or stale candidates remain a hard audit failure.

## Decision boundary

No Asterisk restart, reload, configuration edit, listener change, firewall change, packet capture, tracer attachment, package installation, call, or public activation is justified by this failed run.
