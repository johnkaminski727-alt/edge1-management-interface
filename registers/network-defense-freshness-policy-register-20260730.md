# Network Defense Freshness Policy Register

Date: 2026-07-30  
Classification: internal, sanitized  
System: Edge1 / WW.CX Network Defense  
Repository state: merged through PR #126 as `711952afb053fa3bd50c390516fa7b58f3943985`

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

| Asset | Change | Repository state |
| --- | --- | --- |
| `server/network_defense_freshness_exporter.py` | Final layered wrapper sets only the network-source stale limit to 600 seconds | Merged |
| `deploy/systemd/wwcx-network-defense.service` | Invokes the schedule-aware wrapper | Merged |
| `tests/test_network_defense_freshness_policy.py` | Verifies threshold, boundary behavior, unchanged peer thresholds, service hardening, and no command/network execution | Merged and passed |
| Legacy layered-deployment validators | Verify the freshness -> nftables -> Fail2ban -> DNS chain | Merged and passed |
| `docs/security/network-defense-freshness-policy-20260730.md` | Records evidence, rationale, limits, validation, and deployment boundary | Merged |

## Acceptance contract

- Network source stale threshold is exactly 600 seconds.
- Seven-minute-old network data remains fresh.
- Data older than ten minutes is stale.
- Other source thresholds remain unchanged.
- No timer or producer behavior changes.
- No traffic-control, authentication, certificate, DNS, firewall, Fail2ban, routing, proxy, IDS, or reputation-list changes.
- `verified_enforcement_count` semantics remain unchanged.
- `traffic_controls_changed` remains false.

## Repository validation and merge

| Validation | State |
| --- | --- |
| Focused implementation review | Passed |
| Static repository inspection | Passed |
| Targeted and full Python validation | Passed |
| JSON, shell, and JavaScript validation | Passed |
| Shared collector Python 3.6 validation | Passed |
| Exact-head `Validate repository` | Run 610, success |
| Exact-head `Edge1 Operator Validation` | Run 442, success |
| Review threads | None unresolved |
| Mergeability | Verified before merge |
| Implementation merge | `711952afb053fa3bd50c390516fa7b58f3943985` |
| Edge1 live activation | Not performed or claimed |
| Live endpoint acceptance | Not performed or claimed |

## Rollback

Repository rollback is removal of the wrapper and restoration of the prior systemd `ExecStart`. A future live rollback must restore the prior service file, run daemon reload, execute the prior exporter, and verify the public snapshot. No producer timer or security control needs rollback because none is changed.

## Safety boundary

This register accepts repository implementation only. It does not authorize or claim any live change to DNS, Unbound, RPZ, nftables, firewall rules, Fail2ban jails/actions, routing, proxying, IDS rules, reputation lists, authentication boundaries, certificates, or production traffic.
