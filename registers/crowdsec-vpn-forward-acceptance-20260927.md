# CrowdSec VPN forwarding acceptance register — 2026-09-27

**Evidence:** operator-provided Edge1 and Windows transcripts; acceptance details in [VPN forwarding closeout](../docs/security/crowdsec-vpn-forward-production-acceptance-20260927.md). Earlier dual-stack INPUT acceptance remains separately documented.

| ID | Control | Status | Evidence |
|---|---|---|---|
| VF-01 | UFW/WireGuard/NAT/CrowdSec preflight | Passed | 134 |
| VF-02 | Dedicated 2-rule forward hook and idempotent rollback | Passed | 135–136 |
| VF-03 | Windows internet route through WireGuard | Passed | 137 |
| VF-04 | Controlled reserved-destination packet drop | Passed: 4 packets / 240 bytes | 138–140 |
| VF-05 | Independent emergency timer and test cleanup | Passed | 136, 140 |
| VF-06 | Dependency-ordered service and enabled-state rollback | Passed | 141–142 |
| VF-07 | Permanent activation and fresh VPN connectivity | Passed | 143–144 |
| VF-08 | Production reboot and three-hook restoration | Passed | 145–146 |
| VF-09 | IPv6 VPN forwarded-traffic filtering | Not enabled | IPv6 forwarding intentionally disabled |
| VF-10 | Inbound blacklisted-source packet drop | Not exercised | Inbound drop counter remained 0 during test |
| VF-11 | Live-hook UFW reload | Open | Require timed rollback and external access test |
| VF-12 | Feed freshness, false-positive and exception governance | Open | Monitoring/operating procedure |
| VF-13 | Edge1 private-model knowledge import | Not verified | ChatGPT Library archiving does not prove private-index ingestion |

Last observed 2026-09-27 after 04:03 UTC reboot: all ten relevant services active/enabled, four CrowdSec units reported Result=success/exit 0, IPv4/IPv6 INPUT and IPv4 FORWARD hooks active; snapshot IPv4=23,006 and IPv6=364. This is a single-time observation, not continuous health monitoring.
