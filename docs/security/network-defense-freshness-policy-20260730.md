# Network Defense Freshness Policy

Date: 2026-07-30  
System: Edge1 / WW.CX Network Defense  
Status: repository implementation pending CI and review

## Objective

Make source staleness reporting reflect the actual read-only producer schedules without changing any producer timer, service, security control, authentication boundary, or production traffic.

## Evidence

The relevant repository schedules are:

| Source or consumer | Normal schedule |
| --- | ---: |
| `wwcx-operations-network.timer` | 300 seconds |
| `wwcx-security-operations.timer` | 120 seconds |
| `wwcx-security-correlation.timer` | 60 seconds |
| `wwcx-network-defense.timer` | 60 seconds plus up to 10 seconds randomized delay |

The prior Network Defense base exporter used a 300-second stale limit for `operations-network.json`. Because the producer itself runs every 300 seconds, a healthy source can exceed that limit before its next normal publication is consumed.

The existing Security observability live-acceptance procedure uses a ten-minute default freshness ceiling. A 600-second Network Defense threshold therefore:

- permits one normal five-minute producer interval plus consumer scheduling delay;
- marks the source stale after two missed producer intervals;
- remains consistent with the established live-acceptance ceiling;
- avoids weakening the faster thresholds for Security Operations, Security Correlation, operations-center telemetry, Spamhaus live state, Fail2ban live state, or nftables live state.

## Implementation

`server/network_defense_freshness_exporter.py` wraps the final layered exporter and changes only:

```text
network stale_after_seconds: 300 -> 600
```

The systemd service invokes this final wrapper. The service remains a capability-free, AF_UNIX-only, read-only observer except for its existing status publication directory.

## Explicit non-changes

This phase does not modify:

- `wwcx-operations-network.timer` or any other timer interval;
- DNS, Unbound, RPZ, nftables, firewall, Fail2ban, routing, proxy, IDS rules, reputation lists, certificates, or authentication;
- source document contents, collection commands, or privacy contracts;
- enforcement state or `verified_enforcement_count`;
- `traffic_controls_changed`, which remains false.

## Validation requirements

Repository acceptance requires:

- the Network Defense threshold is exactly 600 seconds;
- a seven-minute network snapshot remains fresh;
- a snapshot older than ten minutes is stale;
- every other existing source threshold remains unchanged;
- the systemd unit invokes the freshness wrapper and retains an empty capability set and AF_UNIX-only boundary;
- the wrapper contains no command or network execution;
- targeted tests and the full repository validation pass;
- both exact-head CI workflows pass.

## Deployment boundary

No live deployment is included in the repository phase. Edge1 activation requires a separate terminal session, clean authoritative `main`, bounded installation or file deployment, service verification, endpoint verification, and protected evidence capture. No live claim may be made from repository CI alone.
