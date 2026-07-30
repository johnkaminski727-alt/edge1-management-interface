# nftables Aggregate Live-State Verifier Register

Date: 2026-07-30  
Classification: internal, sanitized  
System: Edge1 / WW.CX Network Defense

## Trigger

Network Defense previously reported the general firewall layer from normalized event counts only. That did not establish whether a live nftables ruleset was present or expose bounded current object, hook, policy, verdict, and counter aggregates.

## Implemented assets

| Asset | Purpose | State |
| --- | --- | --- |
| `server/nftables_live_state_verifier.py` | Read-only full-ruleset parser that publishes aggregates only | Implemented on feature branch |
| `server/network_defense_nftables_exporter.py` | Final public aggregate-only Network Defense layer | Implemented on feature branch |
| `deploy/systemd/wwcx-nftables-live-state.service` | Hardened root oneshot with `CAP_NET_ADMIN` and netlink only | Implemented on feature branch |
| `deploy/systemd/wwcx-nftables-live-state.timer` | 60-second refresh schedule | Implemented on feature branch |
| `deploy/systemd/wwcx-network-defense.service` | Orders after all dedicated observers and remains capability-free | Updated on feature branch |
| `deploy/install-nftables-live-state-observability.sh` | Rollback-safe activation and evidence capture | Implemented on feature branch |
| `/var/lib/bigbird-networking/nftables/live-state.json` | Sanitized private runtime snapshot | Pending activation |

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

No state in this contract is equivalent to packet-enforcement verification.

## Validation state

| Validation | State |
| --- | --- |
| Ruleset object, family, hook, policy, verdict, element, and counter parsing | Implemented |
| Sensitive fixture names, addresses, interfaces, comments, handles, and expressions excluded | Implemented |
| Read-only command enforcement | Implemented |
| Atomic private `0640` publication | Implemented |
| Public aggregate-only integration | Implemented |
| Stale-source downgrade | Implemented |
| No verified-enforcement increment | Implemented |
| Least-privilege observer service | Implemented |
| Capability-free Network Defense service | Implemented |
| Runtime ordering | Implemented |
| Rollback-safe installer | Implemented |
| Legacy DNS, Spamhaus, and Fail2ban validator compatibility | Implemented |
| Exact-head CI | Pending PR |
| Live Edge1 activation | Pending merge |

## Repository audit trail

A one-byte placeholder was accidentally created on `main` by commit `f954e3395dbecf36cad9dc209cf378eb2dcc986d` before the feature branch existed. Commit `7b79f564f11928a63d5b028ab1e2fe0a61f65e6a` removed it immediately. The implementation branch was then created from corrected `main`. No runtime or production system was changed.

## Planned activation

```bash
cd /opt/edge1-management-interface
git pull --ff-only origin main
sudo bash ./deploy/install-nftables-live-state-observability.sh
```

Expected evidence:

```text
/var/lib/wwcx-deployment-evidence/nftables-live-state/<timestamp>
```

A truthful degraded state is acceptable. The installer must not reload, restart, repair, or otherwise mutate nftables to improve the result.

## Safety boundary

No nftables or firewall mutation, service reload/restart, DNS/resolver/RPZ change, Fail2ban jail/action change, routing, proxy, IDS, authentication, reputation-list, or traffic-control change is included.
