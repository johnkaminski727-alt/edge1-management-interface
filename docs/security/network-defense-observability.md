# Network Defense Observability

## Purpose

The Network Defense module combines sanitized status from existing Edge1 security and networking exporters into one read-only readiness view. It does not install, enable, reload, or modify DNS, firewall, Fail2ban, proxy, routing, or IDS controls.

## Inputs

- `/var/www/edge1-status/operations-network.json`
- `/var/www/edge1-status/security-operations.json`
- `/var/www/edge1-status/security-correlation.json`
- `/var/lib/bigbird/operations-center/latest.json`
- `/var/lib/bigbird-networking/spamhaus/summary.txt`

## Output

`/var/www/edge1-status/network-defense.json`

The output distinguishes:

1. **observed** — sanitized telemetry exists;
2. **feed ready** — reputation feed counters exist;
3. **enforcement verified** — a dedicated verifier confirms an active traffic-control boundary.

The initial implementation intentionally reports no verified enforcement until dedicated verifiers exist.

## Current layer status contract

- **IDS**: consumes Security Operations telemetry.
- **DNS**: reports resolver or normalized DNS-event visibility only.
- **Spamhaus**: reports feed readiness from sanitized counters.
- **Firewall**: reports normalized event visibility only.
- **Fail2ban**: reports normalized event visibility only.
- **Proxy**: reports whether a proxy-event contract exists; it does not install a proxy.

## Privacy and safety

The aggregate excludes packet payloads, credentials, private keys, raw logs, and the full firewall ruleset. It reads existing snapshots and atomically writes one status document.

## Deferred implementation gates

Require separate design, validation, and explicit production authorization:

- Unbound RPZ/local-zone policy enforcement;
- nftables live-state verification;
- Fail2ban jail-status export;
- Squid or another forward proxy installation and routing;
- DNS, firewall, certificate, proxy, or routing changes.

## Validation

```bash
tools/networking/validate-network-defense.sh
```
