# Edge1 Comprehensive Listener Exposure Audit Acceptance — 2026-08-01

## Authoritative evidence

Authenticated operator execution on `edge1.ww.cx` by `wwadmin` with bounded `sudo` elevation.

Initial audit:

```text
/var/lib/wwcx-deployment-evidence/edge1-comprehensive-listener-exposure/20260801T022454Z/audit.txt
SHA-256: fdcfdadcedefb44359f24732d65b8f937a579ca4918cba1282848f7f4b049b3e
```

Supplemental rerun:

```text
/var/lib/wwcx-deployment-evidence/edge1-comprehensive-listener-exposure/20260801T025726Z/audit.txt
SHA-256: 1f5b92a2dd7661c291dd501f20677f28e97b9c39c7bda20bd9bae1a6bf21e4f2
```

Both audits exited `0`, reported four warnings and zero failures, and made no configuration, service, listener, route, certificate, firewall, package, call, container, or traffic change.

## Public network boundary

The authoritative `inet wwcxfw` input chain has policy `drop`. Its observed public-interface allowances are limited to:

- TCP `80` and `443` for public web traffic;
- UDP `51820` for WireGuard;
- established and related traffic;
- ICMP and ICMPv6.

All other new public-interface traffic falls through to the terminal drop path. A separate iptables-nft compatibility chain has policy `accept`, but that does not override a drop verdict from the `wwcxfw` input base chain.

This means wildcard or public-address-bound services are not automatically Internet-reachable. Their effective reachability still depends on the `wwcxfw` path.

The rerun reconfirmed the same firewall boundary. It was a local observation rather than an outside-in Internet scan, so upstream-provider reachability remains a separate verification task.

## Internal WireGuard boundary

The rule `iifname "wg0" accept` permits every service reachable through the WireGuard interface. This includes services that are wildcard-bound and services explicitly bound to `10.77.0.1`.

The current WireGuard boundary is therefore trusted-network broad rather than least-privilege per-service. It is not an immediate public exposure, but it requires an explicit internal-service policy before additional users or peers are admitted.

## Wildcard and direct-address priority inventory

The supplemental rerun confirmed these material non-loopback surfaces:

| Service | Bind | Effective public status | WireGuard status | Priority |
|---|---|---|---|---|
| Apache | TCP `*:80`, `*:443` | explicitly admitted | reachable | intended public ingress |
| WireGuard | UDP `*:51820` | explicitly admitted | transport endpoint | intended public ingress |
| MariaDB/systemd socket | TCP `*:3306` | blocked by `wwcxfw` | reachable | highest attribution and least-privilege priority |
| Node process | TCP `*:8001`, `*:8003` | blocked by `wwcxfw` | reachable | high attribution priority |
| SSH | TCP `0.0.0.0:22`, `[::]:22` | blocked by `wwcxfw` | reachable | administrative exposure review |
| Asterisk HTTPS/WSS | TCP `*:8089` | blocked by `wwcxfw` | reachable | internal telephony/WebSocket surface |
| Kamailio | TCP/UDP `89.147.109.253:5060` | bound to public address but blocked by `wwcxfw` | separately reachable on `10.77.0.1:5060` | telecom activation boundary |
| Asterisk resolver sockets | UDP `*:55539`, `[::]:59177` | blocked by `wwcxfw` | reachable | attributed control-plane sockets |
| Unbound | TCP/UDP `10.77.0.1:53` | not public-bound | reachable | intended VPN DNS, subject to peer policy |

Wildcard MariaDB `3306` and Node `8001`/`8003` are the next read-only attribution targets. No listener or firewall change should be selected until the owning configuration, consumers, service units, and rollback effects are known.

## Asterisk surfaces observed

The audit confirmed these current Asterisk surfaces:

- AMI TCP `127.0.0.1:5038`;
- HTTP TCP `127.0.0.1:8088`;
- HTTPS/WebSocket TCP wildcard `8089`, effectively reachable from loopback and WireGuard but blocked for new public-interface connections;
- PJSIP UDP `127.0.0.1:5061`;
- persistent resolver/control-plane UDP wildcard sockets on ports `55539` and `59177`.

Subsequent focused audits mapped ports `55539` and `59177` to Asterisk FDs `15` and `17`, established that they are in the kernel ephemeral range rather than the configured RTP range, and correlated them with the live `unbound_resolver_thread` and `res_resolver_unbound.so`. Their accepted attribution is persistent Asterisk resolver/control-plane sockets, overwhelmingly likely libunbound. They are not active RTP or STUN sockets.

## Apache surface

Apache is the intentional public ingress on TCP `80` and `443`. Enabled virtual hosts include:

- `edge1.ww.cx`, with aliases `pbx.ww.cx` and `sip.ww.cx`;
- `interconnect.ww.cx`;
- `portal.ww.cx`;
- `vpn.ww.cx` on TLS.

Apache reports runtime user and group `asterisk:asterisk`. This creates a privilege and ownership coupling between the public web server and the telephony service account. It is not changed by this audit, but it should receive a separate least-privilege review after the higher-priority wildcard service attribution is complete.

## Containers

Neither Docker nor Podman is installed, so no container-published ports were present.

## Decision boundary

Accepted:

- the public allow-list remains TCP `80`, TCP `443`, and UDP `51820`;
- Asterisk `8089` is a legitimate HTTPS/WSS surface but is currently internal-only by effective firewall policy;
- the broad WireGuard trust boundary requires later hardening review;
- Asterisk high UDP sockets are attributed resolver/control-plane sockets rather than RTP;
- MariaDB `3306` and Node `8001`/`8003` require immediate read-only ownership and consumer attribution;
- Kamailio public-address binding remains inactive at the firewall boundary;
- Apache is the public front door and currently runs as the `asterisk` account;
- continued offline-only alerting laboratory operation.

Not authorized or performed:

- listener, firewall, WireGuard, Apache, database, Node, Asterisk, PJSIP, Kamailio, certificate, service, package, call, CAP-feed, page, or attention-tone changes;
- an external Internet scan;
- attaching `strace`, `gdb`, or another intrusive runtime tracer to a service.
