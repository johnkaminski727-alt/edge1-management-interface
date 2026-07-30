# Edge1 Security Completion Programs Register

Date: 2026-07-30  
Authorization: Edge1 Security Completion Programs authorized handoff  
Repository baseline: `83fdb08670f3b65dcdee705e440f1441efd5531e`

## Repository implementation

| Program | Repository state | Live state |
|---|---|---|
| Protected Suricata retention | Implemented with root-only SQLite, deterministic deduplication, bounded pruning, integrity verification, systemd timer, rollback, and evidence capture | Awaiting authenticated Edge1 execution |
| Minimized public summary | Existing allowlist exporter packaged as hardened systemd oneshot/timer and isolated publication tree | Awaiting authenticated Edge1 execution |
| Authenticated detailed operations | Apache form/session boundary, encrypted session-cookie key file, approved password-file provider, fail-closed checks, audit log, response rate limit, and browser-equivalent acceptance | Awaiting authenticated Edge1 execution and protected acceptance credential file |
| Public-boundary cutover | Authentication-first staging, archive-before-withdrawal, minimized alias, anonymous detailed-route 404 checks, authenticated equivalence, rollback, and evidence | Awaiting authenticated Edge1 execution |

## Immutable safety facts

- No raw Suricata EVE retention.
- No packet payload, credentials, private keys, or arbitrary nested metadata.
- No new public listener.
- No DNS, Unbound, RPZ, nftables, firewall, routing, IDS-rule, reputation-list, certificate, or traffic-control change.
- Detailed files and protected evidence are not deleted.
- Cutover is blocked until authenticated detailed access succeeds.
- Rollback preserves the retention database and detailed archive.

## Validation

Repository validation entry point:

```text
tests/validate_edge1_security_completion.py
```

Live acceptance is not recorded until all four protected evidence directories exist and both public and authenticated endpoint matrices pass.
