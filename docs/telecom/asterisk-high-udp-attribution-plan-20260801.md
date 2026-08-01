# Asterisk High UDP Socket Attribution Plan — 2026-08-01

## Objective

Attribute the Asterisk-owned wildcard UDP sockets observed on ports `55539` and `59177` without changing runtime state or assuming they are RTP.

## Evidence inputs

- comprehensive listener exposure audit:
  - `/var/lib/wwcx-deployment-evidence/edge1-comprehensive-listener-exposure/20260801T022454Z/audit.txt`
  - SHA-256 `fdcfdadcedefb44359f24732d65b8f937a579ca4918cba1282848f7f4b049b3e`
- Asterisk PID observed: `1651722`
- zero active channels and calls during preceding audits
- public firewall policy admits only TCP `80`, TCP `443`, and UDP `51820`
- WireGuard currently accepts all inbound services on `wg0`

## Read-only attribution method

The audit will:

1. capture all Asterisk-owned UDP sockets with process and inode metadata;
2. map `/proc/<pid>/fd` socket inodes to `/proc/net/udp` and `/proc/net/udp6`;
3. use `lsof` only when already installed;
4. inspect the configured and runtime RTP range;
5. compare each high port with the RTP range and kernel ephemeral range;
6. inspect loaded RTP, STUN, ICE-related, resolver, PJSIP, and WebSocket modules;
7. print only allow-listed configuration fields and configuration hashes;
8. preserve current network namespace and routing metadata.

## Prohibited methods

The audit must not:

- attach `strace`, `gdb`, eBPF probes, or another runtime tracer;
- run packet capture;
- send test packets or conduct an active port scan;
- reload or restart Asterisk;
- rotate logs;
- edit generated or custom configuration;
- change firewall, WireGuard, routes, listeners, packages, calls, or traffic.

## Interpretation rules

- A port inside the configured RTP range is only a media candidate, not proof of an active RTP session.
- A port inside the kernel ephemeral range is only an ephemeral-socket candidate.
- Loaded STUN, ICE, resolver, or PJSIP modules provide context but not definitive ownership.
- Definitive attribution requires agreement among process file-descriptor mapping, socket metadata, configured ranges, and runtime module state.
- If read-only metadata remains insufficient, stop before intrusive tracing and plan a controlled maintenance-window capture around a future Asterisk restart.
