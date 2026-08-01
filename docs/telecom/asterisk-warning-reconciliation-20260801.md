# Asterisk Warning Reconciliation — 2026-08-01

## Live evidence

Authenticated operator audit on `edge1.ww.cx` at `2026-08-01T00:14:55Z`.

Evidence:

```text
/var/lib/wwcx-deployment-evidence/asterisk-warning-followup/20260801T001432Z/audit.txt
SHA-256: 033bf4ac95c99cd765cee36a21749b7e8eead4745e18da8ab6c0b9c5b8e042ad
```

## Accepted observations

- Asterisk `22.10.1` remained healthy for more than 36 minutes after update.
- Zero active calls/channels and zero processed calls were observed.
- Asterisk owns UDP `127.0.0.1:5061`.
- `pjsip show transports` and `pjsip show endpoints` both returned no objects.
- `pjsip.transports.conf` defines `[0.0.0.0-udp]` at `0.0.0.0:5060`.
- `pjsip.transports_custom.conf` defines the same section name at `127.0.0.1:5061`.
- Asterisk startup persistence is disabled: all SysV runlevel links are `K01asterisk`; no `S` link was observed.
- HTTPS is enabled on `[::]:8089`; a local TLS 1.3 handshake succeeded.
- The 8089 certificate identifies `edge1.ww.cx` but is self-signed.
- No explicit nftables references to ports 5038, 5061, 8088, or 8089 were found.
- No alert delivery, CAP source, endpoint, route, page, or tone transmission was enabled.

## Classification

### PJSIP transport discrepancy

Configuration contains duplicate transport section names across generated and custom files. The listener proves a SIP stack owns `127.0.0.1:5061`, but the PJSIP object registry does not expose a transport object. Do not edit the generated FreePBX file. Resolve include order and channel-driver ownership before changing the custom definition.

### Boot persistence defect

This is a confirmed operational defect, not merely an ambiguous warning. The current running process will not be assumed to return after reboot. Enabling startup is a separate conditional change with rollback evidence and no service restart required.

### TCP 8089 exposure

TLS is functional locally. Wildcard binding is confirmed, but external reachability is not established by this audit. Firewall chain policy, intended WebSocket/metrics consumers, and certificate trust must be resolved before changing the listener.

## Next gates

1. Run a second read-only audit of PJSIP include order, channel types, HTTP configuration, nftables input-chain policy, certificate metadata, and intended consumers.
2. Prepare a guarded Asterisk boot-enablement script that records existing links, applies the narrow startup-policy change, validates `S` links, and supports rollback without restarting Asterisk.
3. Decide whether 8089 should remain wildcard-bound, be restricted to WireGuard/private addresses, or be reverse-proxied with a trusted certificate.
4. Keep all CAP feeds, Actual alerts, call/page delivery, and alert-tone transmission blocked.
