# Network Defense Freshness Policy Register

Date: 2026-07-30  
Classification: internal, sanitized  
System: Edge1 / WW.CX Network Defense

## Trigger

The Network Defense base exporter treated `operations-network.json` as stale after 300 seconds, while its authoritative producer timer also runs every 300 seconds. The one-minute Network Defense consumer and its randomized delay can therefore observe healthy producer data beyond the prior threshold.

## Evidence basis

| Evidence | Verified value |
| --- | ---: |
| Operations network producer interval | 300 seconds |
| Network Defense consumer interval | 60 seconds |
| Network Defense randomized delay | up to 10 seconds |
| Existing live-acceptance freshness ceiling | 600 seconds |

## Registered change

| Asset | Change | State |
| --- | --- | --- |
| `server/network_defense_freshness_exporter.py` | Final layered wrapper sets only the network-source stale limit to 600 seconds | Implemented on feature branch |
| `deploy/systemd/wwcx-network-defense.service` | Invokes the schedule-aware wrapper | Implemented on feature branch |
| `tests/test_network_defense_freshness_policy.py` | Verifies threshold, boundary behavior, unchanged peer thresholds, service hardening, and no command/network execution | Implemented on feature branch |
| `docs/security/network-defense-freshness-policy-20260730.md` | Records evidence, rationale, limits, validation, and deployment boundary | Implemented on feature branch |

## Acceptance contract

- Network source stale threshold is exactly 600 seconds.
- Seven-minute-old network data remains fresh.
- Data older than ten minutes is stale.
- Other source thresholds remain unchanged.
- No timer or producer behavior changes.
- No traffic-control, authentication, certificate, DNS, firewall, Fail2ban, routing, proxy, IDS, or reputation-list changes.
- `verified_enforcement_count` semantics remain unchanged.
- `traffic_controls_changed` remains false.

## Validation state

| Validation | State |
| --- | --- |
| Focused implementation review | Passed |
| Static repository inspection | Passed |
| Targeted unit tests | Pending exact-head CI |
| Full repository validation | Pending exact-head CI |
| Edge1 live activation | Not performed |
| Live endpoint acceptance | Not performed |

## Rollback

Repository rollback is removal of the wrapper and restoration of the prior systemd `ExecStart`. A future live rollback must restore the prior service file, run daemon reload, execute the prior exporter, and verify the public snapshot. No producer timer or security control needs rollback because none is changed.

## Safety boundary

This register describes read-only repository work only. It does not authorize or claim any live change to DNS, Unbound, RPZ, nftables, firewall rules, Fail2ban jails/actions, routing, proxying, IDS rules, reputation lists, authentication boundaries, certificates, or production traffic.
