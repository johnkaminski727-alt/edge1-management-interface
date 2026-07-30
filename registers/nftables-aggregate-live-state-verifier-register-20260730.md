# nftables Aggregate Live-State Verifier Register

Date: 2026-07-30  
Classification: internal, sanitized  
System: Edge1 / WW.CX Network Defense

## Trigger

Network Defense previously reported the general firewall layer from normalized event counts only. That did not establish whether a live nftables ruleset was present or expose bounded current object, hook, policy, verdict, and counter aggregates.

## Implemented assets

| Asset | Purpose | State |
| --- | --- | --- |
| `server/nftables_live_state_verifier.py` | Read-only full-ruleset parser that publishes aggregates only | Merged and deployed |
| `server/network_defense_nftables_exporter.py` | Final public aggregate-only Network Defense layer | Merged and deployed |
| `deploy/systemd/wwcx-nftables-live-state.service` | Hardened root oneshot with `CAP_NET_ADMIN` and netlink only | Installed |
| `deploy/systemd/wwcx-nftables-live-state.timer` | 60-second refresh schedule | Installed and enabled |
| `deploy/systemd/wwcx-network-defense.service` | Orders after all dedicated observers and remains capability-free | Updated live |
| `deploy/install-nftables-live-state-observability.sh` | Rollback-safe activation and evidence capture | Executed successfully |
| `/var/lib/bigbird-networking/nftables/live-state.json` | Sanitized private runtime snapshot | Live |

## Contract

- Schema: `wwcx.nftables-aggregate-live-state.v1`.
- Read-only commands: `nft -j list ruleset` and `systemctl show nftables.service ...`.
- Fixed allowlists: families, hooks, policies, and verdict categories.
- Published values: aggregate object counts, element counts, rule/verdict counts, and counter packet/byte totals.
- Safety flags: `read_only: true`, `enforcement_verified: false`, `traffic_controls_changed: false`.

## Privacy boundary

Allowed:

- numeric aggregate counts;
- fixed allowlisted category labels;
- sanitized service and observation states.

Excluded everywhere:

- table, chain, set, map, object, or jump-target names;
- addresses, prefixes, ports, interfaces, and devices;
- set and map elements;
- rule expressions, values, comments, handles, and priorities;
- the full ruleset and raw command output;
- credentials and private keys.

## State model

| State | Meaning |
| --- | --- |
| `ruleset_observed` | Tables, chains, and rules observed and reduced to sanitized aggregates |
| `partial` | Ruleset present but aggregate topology incomplete |
| `empty` | Read query succeeded with no tables |
| `not_installed` | `nft` command unavailable |
| `unavailable` | Ruleset query or JSON unavailable |

No state in this contract is equivalent to general packet-enforcement verification.

## Accepted live result

Implementation merged through PR #124 and was deployed successfully on Edge1.

```json
{
  "nftables_state": "ruleset_observed",
  "nftables_observed": true,
  "nftables_enforcement_verified": false,
  "tables": 4,
  "chains": 14,
  "base_chains": 7,
  "rules": 46,
  "sets": 6,
  "maps": 0,
  "counter_packets": 1866364147,
  "counter_bytes": 4478865062835,
  "verified_enforcement_count": 1,
  "overall_state": "limited",
  "available_sources": 8,
  "source_count": 9,
  "dns_policy_state": "not_staged",
  "dns_enforcement_enabled": false,
  "traffic_controls_changed": false
}
```

The private observer snapshot taken immediately before the Network Defense refresh reported 1,866,363,293 packets and 4,478,862,225,755 bytes. The public snapshot increased to 1,866,364,147 packets and 4,478,865,062,835 bytes as live counters advanced. Topology counts remained identical.

The accepted state proves current sanitized aggregate visibility only. It does not verify general policy correctness or packet-path enforcement. The one verified enforcement source remains Spamhaus.

## Evidence

```text
/var/lib/wwcx-deployment-evidence/nftables-live-state/20260730T090522Z
/var/lib/wwcx-deployment-evidence/nftables-live-state/20260730T090522Z/acceptance-summary.json
```

## Validation state

| Validation | State |
| --- | --- |
| Ruleset object, family, hook, policy, verdict, element, and counter parsing | Passed |
| Sensitive fixture names, addresses, interfaces, comments, handles, and expressions excluded | Passed |
| Read-only command enforcement | Passed |
| Atomic private `0640` publication | Passed live |
| Public aggregate-only integration | Passed live |
| Stale-source downgrade | Passed |
| No verified-enforcement increment | Passed live |
| Least-privilege observer service | Passed live |
| Capability-free Network Defense service | Passed live |
| Runtime ordering | Passed live |
| Rollback-safe installer | Passed |
| Legacy DNS, Spamhaus, and Fail2ban validator compatibility | Passed |
| Exact-head CI | Passed |
| Live Edge1 activation | Accepted |

## Repository audit trail

A one-byte placeholder was accidentally created on `main` by commit `f954e3395dbecf36cad9dc209cf378eb2dcc986d` before the feature branch existed. Commit `7b79f564f11928a63d5b028ab1e2fe0a61f65e6a` removed it immediately. The implementation branch was then created from corrected `main`. No runtime or production system was changed.

## Safety boundary

No nftables or firewall mutation, service reload/restart, DNS/resolver/RPZ change, Fail2ban jail/action change, routing, proxy, IDS, authentication, reputation-list, or traffic-control change was included or performed.
