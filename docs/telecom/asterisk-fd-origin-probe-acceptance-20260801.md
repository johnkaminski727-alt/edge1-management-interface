# Asterisk File-Descriptor Origin Probe Acceptance — 2026-08-01

## Authoritative evidence

Authenticated operator execution on `edge1.ww.cx` by `wwadmin` with bounded `sudo` elevation.

```text
/var/lib/wwcx-deployment-evidence/asterisk-fd-origin-probe/20260801T024907Z/audit.txt
SHA-256: ebb8ec071b28c10098aac07ff5746f99a7ea2c969c72f60a087f06aeb34d1f0c
```

The probe exited `0`, reported one warning and zero failures, and made no tracer, packet-capture, configuration, service, listener, route, certificate, firewall, package, call, logger, module, container, or traffic change.

## Accepted findings

The probe reconfirmed these live Asterisk sockets:

- FD `15`: IPv4 wildcard UDP `0.0.0.0:55539`, inode `23758409`;
- FD `17`: IPv6-only wildcard UDP `[::]:59177`, inode `23758410`;
- FD `18`: loopback UDP `127.0.0.1:5061`, inode `23758408`.

Asterisk was active with zero channels, zero calls and zero processed calls.

The production build does not expose `core show fd`:

```text
No such command 'core show fd'.
core_show_fd_available=no
```

This is consistent with a build that lacks `DEBUG_FD_LEAKS`. Direct source-file creation records for FDs `15` and `17` are therefore unavailable without intrusive tracing or a differently instrumented build.

## Resolver attribution

The live thread registry exposed:

```text
unbound_resolver_thread started at res_resolver_unbound.c unbound_resolver_start()
```

At the same time:

- `res_resolver_unbound.so` was running with use count `1`;
- `res_rtp_asterisk.so` was running with use count `0`;
- `res_stun_monitor.so` was running with use count `0`;
- RTP was configured for UDP `10000-20000`, while ports `55539` and `59177` are kernel-ephemeral ports;
- STUN was disabled;
- no calls or channels were active.

The accepted classification is therefore:

> persistent Asterisk resolver/control-plane sockets, overwhelmingly likely to be owned by the libunbound resolver path.

This is a strong operational attribution rather than an exact socket-creation call-site proof. No restart, module unload, tracer attachment or packet capture is justified solely to raise that confidence further.

## Exposure boundary

The sockets remain wildcard-bound inside the process, but the authoritative public input policy admits only TCP `80`, TCP `443` and UDP `51820`. New public-interface traffic to UDP `55539` and `59177` is dropped.

The broad rule `iifname "wg0" accept` means authenticated WireGuard peers can reach wildcard services. That remains an internal least-privilege issue, not a public Internet exposure.

## Diagnostic source-label correction

The probe resolved PID `1651722` correctly from `/run/asterisk/asterisk.pid`, but printed an empty `pid_source=` field because the original shell implementation used command substitution and lost the variable assignment in a subshell.

The corrected script now preserves PID and source in parent-shell variables. This display defect does not invalidate the socket, thread or module evidence above.

## New lifecycle concern

Socket metadata placed the Asterisk process under:

```text
/user.slice/user-1000.slice/session-21312.scope
```

while `asterisk.service` reported active and systemd `MainPID` remained unresolved. This may indicate SysV compatibility or manual/session-scoped process ownership rather than a normal system service cgroup.

A separate read-only lifecycle audit is required before relying on service restart, logout survival or reboot recovery semantics. No restart or service migration is authorized by this evidence alone.
