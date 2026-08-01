# Asterisk High UDP Socket Attribution Acceptance — 2026-08-01

## Authoritative evidence

Authenticated operator execution on `edge1.ww.cx` by `wwadmin` with bounded `sudo` elevation.

```text
/var/lib/wwcx-deployment-evidence/asterisk-high-udp-attribution/20260801T024404Z/audit.txt
SHA-256: 75e2875a824cfe08edb95a65950408595647a98c50315451268da831950a6ef1
```

The corrected audit exited `0`, reported zero warnings and zero failures, and made no tracer, packet-capture, configuration, service, listener, route, certificate, firewall, package, call, logger, container, or traffic change.

## Accepted socket mapping

The live Asterisk process was resolved from `/run/asterisk/asterisk.pid`:

```text
PID 1651722
/usr/sbin/asterisk -f -U asterisk -G asterisk -vvvg -c
```

The relevant UDP sockets were mapped directly to process file descriptors and kernel socket inodes:

| FD | Family and bind | Inode | Classification |
|---:|---|---:|---|
| 15 | IPv4 `0.0.0.0:55539` | `23758409` | kernel ephemeral range |
| 17 | IPv6 `[::]:59177`, `v6only:1` | `23758410` | kernel ephemeral range |
| 18 | IPv4 `127.0.0.1:5061` | `23758408` | loopback PJSIP socket |

The process and sockets share the host network namespace.

## Range and feature classification

- Asterisk RTP range is UDP `10000-20000`.
- The kernel ephemeral range is `32768-60999`.
- Ports `55539` and `59177` are inside the kernel ephemeral range and outside the configured RTP range.
- Zero active channels, zero active calls, and zero processed calls were observed.
- `res_rtp_asterisk` was loaded with use count `0`.
- STUN was disabled and `res_stun_monitor` had use count `0`.
- `res_resolver_unbound` was loaded with use count `1`.
- One persistent IPv4 and one persistent IPv6 wildcard ephemeral socket were present from the running Asterisk process.

These facts exclude the two high ports from the configured RTP media range and make active media or STUN ownership implausible. Their shape and module state are consistent with persistent libunbound resolver/control-plane sockets. This is the leading attribution, but the exact socket-creation call site has not yet been proven.

## Exposure classification

The sockets are wildcard-bound at the process level, but the authoritative `inet wwcxfw` input chain admits new public-interface traffic only to TCP `80`, TCP `443`, and UDP `51820`. New public traffic to UDP `55539` and `59177` is therefore dropped.

The sockets remain reachable from WireGuard because the current policy broadly accepts all traffic arriving through `wg0`. That is an internal trust-boundary issue, not a public exposure.

## Remaining bounded check

Asterisk can expose `core show fd` when built with `DEBUG_FD_LEAKS`. If available, that command may identify the source file and function that created FDs `15` and `17`. A read-only probe should:

- verify whether `core show fd` is compiled in;
- print only the relevant FD records;
- inspect safe `/proc/<pid>/fdinfo` fields;
- correlate resolver-related thread and module state;
- avoid tracing, packet capture, reloads, module unloads, or service restarts.

If the build does not include `DEBUG_FD_LEAKS`, the accepted classification remains `ephemeral resolver/control-plane sockets, most likely libunbound`, without claiming exact module proof.

## Decision boundary

Accepted:

- the evidence and SHA-256 above;
- direct PID, FD, inode, address-family, and port mapping;
- exclusion from the configured RTP range;
- absence of public reachability under the observed firewall policy;
- resolver/control-plane as the leading attribution;
- continued internal-only and offline alerting posture.

Not authorized or performed:

- Asterisk restart, reload, module unload, or configuration change;
- firewall or WireGuard policy changes;
- packet capture, tracer attachment, or active scan;
- public activation of SIP, RTP, WebSocket, ARI, AMI, CAP feeds, calls, pages, or attention tones.
