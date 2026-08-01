# Edge1 Comprehensive Listener Exposure Audit Acceptance — 2026-08-01

## Authoritative evidence

Authenticated operator execution on `edge1.ww.cx` by `wwadmin` with bounded `sudo` elevation.

```text
/var/lib/wwcx-deployment-evidence/edge1-comprehensive-listener-exposure/20260801T022454Z/audit.txt
SHA-256: fdcfdadcedefb44359f24732d65b8f937a579ca4918cba1282848f7f4b049b3e
```

The audit exited `0`, reported four warnings and zero failures, and made no configuration, service, listener, route, certificate, firewall, package, call, container, or traffic change.

## Public network boundary

The authoritative `inet wwcxfw` input chain has policy `drop`. Its observed public-interface allowances are limited to:

- TCP `80` and `443` for public web traffic;
- UDP `51820` for WireGuard;
- established and related traffic;
- ICMP and ICMPv6.

All other new public-interface traffic falls through to the terminal drop path. A separate iptables-nft compatibility chain has policy `accept`, but that does not override a drop verdict from the `wwcxfw` input base chain.

This means wildcard or public-address-bound services are not automatically Internet-reachable. Their effective reachability still depends on the `wwcxfw` path.

## Internal WireGuard boundary

The rule `iifname "wg0" accept` permits every service reachable through the WireGuard interface. This includes services that are wildcard-bound and services explicitly bound to `10.77.0.1`.

The current WireGuard boundary is therefore trusted-network broad rather than least-privilege per-service. It is not an immediate public exposure, but it requires an explicit internal-service policy before additional users or peers are admitted.

## Asterisk surfaces observed

The audit confirmed these current Asterisk surfaces:

- AMI TCP `127.0.0.1:5038`;
- HTTP TCP `127.0.0.1:8088`;
- HTTPS/WebSocket TCP wildcard `8089`, effectively reachable from loopback and WireGuard but blocked for new public-interface connections;
- PJSIP UDP `127.0.0.1:5061`;
- high UDP wildcard sockets on ports `55539` and `59177`.

The high UDP sockets are not admitted from the public interface under the observed firewall policy. They are reachable from WireGuard because `wg0` is broadly accepted. Their owning Asterisk feature or module has not yet been attributed.

Do not label these sockets as RTP solely from their protocol. Their ports are outside the usual default Asterisk RTP range and may instead be ephemeral sockets associated with ICE/STUN, DNS resolution, PJSIP, or another module. A focused read-only attribution audit is required.

## Apache surface

Apache is the intentional public ingress on TCP `80` and `443`. Enabled virtual hosts include:

- `edge1.ww.cx`, with aliases `pbx.ww.cx` and `sip.ww.cx`;
- `interconnect.ww.cx`;
- `portal.ww.cx`;
- `vpn.ww.cx` on TLS.

Apache reports runtime user and group `asterisk:asterisk`. This creates a privilege and ownership coupling between the public web server and the telephony service account. It is not changed by this audit, but it should receive a separate least-privilege review after listener attribution is complete.

## Containers

Neither Docker nor Podman is installed, so no container-published ports were present.

## Decision boundary

Accepted:

- the public allow-list remains TCP `80`, TCP `443`, and UDP `51820`;
- Asterisk `8089` is a legitimate HTTPS/WSS surface but is currently internal-only by effective firewall policy;
- the broad WireGuard trust boundary requires later hardening review;
- the two high UDP sockets require feature and range attribution;
- Apache is the public front door and currently runs as the `asterisk` account;
- continued offline-only alerting laboratory operation.

Not authorized or performed:

- listener, firewall, WireGuard, Apache, Asterisk, PJSIP, certificate, service, package, call, CAP-feed, page, or attention-tone changes;
- an external Internet scan;
- attaching `strace`, `gdb`, or another intrusive runtime tracer to Asterisk.
