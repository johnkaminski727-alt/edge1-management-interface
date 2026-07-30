# nftables Aggregate Live-State Observability

Date: 2026-07-30  
System: Edge1 / WW.CX Network Defense  
Status: deployed and accepted

## Objective

Publish bounded current topology and counter aggregates for the live Edge1 nftables ruleset without changing nftables, firewall policy, sets, rules, chains, DNS, routing, Fail2ban, proxy, IDS, authentication, or traffic controls.

The prior Network Defense firewall card used normalized event counts only. It could not distinguish absent event telemetry from a present live ruleset or show bounded object, hook, policy, verdict, and counter totals.

## Contract

Authoritative verifier:

```text
server/nftables_live_state_verifier.py
```

Runtime snapshot:

```text
/var/lib/bigbird-networking/nftables/live-state.json
```

Contract:

```text
wwcx.nftables-aggregate-live-state.v1
```

The verifier executes only:

```text
nft -j list ruleset
systemctl show nftables.service ...
```

No `add`, `delete`, `flush`, `insert`, `replace`, `monitor`, or file-load operation is permitted.

## Published evidence

Allowed in the private verifier snapshot and public aggregate view:

- counts of tables, chains, rules, sets, maps, named counters, limits, quotas, flowtables, and other bounded object classes;
- counts by nftables family using a fixed allowlist;
- base-chain counts by fixed hook and policy allowlists;
- rule counts by fixed verdict allowlist;
- total set and map element counts without elements or names;
- aggregate counter statement, packet, and byte totals;
- sanitized `nftables.service` state labels;
- bounded observation state and error labels.

Excluded:

- table, chain, set, map, counter, flowtable, object, or jump-target names;
- addresses, prefixes, ports, interfaces, devices, or client identifiers;
- set and map elements;
- rule expressions, match values, comments, handles, priorities, or jump targets;
- the full ruleset or raw command output;
- credentials and private keys.

## Truthful states

- `ruleset_observed`: tables, chains, and rules were observed and reduced to sanitized aggregates;
- `partial`: a ruleset exists but aggregate topology is incomplete;
- `empty`: the read query succeeded and returned no tables;
- `not_installed`: the `nft` command is unavailable;
- `unavailable`: the live ruleset query failed or returned unusable data.

All states keep:

```json
{
  "enforcement_verified": false,
  "traffic_controls_changed": false
}
```

General ruleset topology and counters do not independently prove policy correctness, intended enforcement, or that every packet path traverses a particular rule.

## Capability and service boundary

`wwcx-nftables-live-state.service` runs as root and receives only `CAP_NET_ADMIN`, because nftables read access uses netlink. It is restricted to `AF_UNIX` and `AF_NETLINK`, strict filesystem protection, and write access only under:

```text
/var/lib/bigbird-networking/nftables
```

The private snapshot is mode `0640` under a mode `0750` directory.

`wwcx-network-defense.service` remains capability-free and reads only the sanitized snapshot through `server/network_defense_nftables_exporter.py`. The final wrapper preserves the existing DNS-aware, Spamhaus-aware, and Fail2ban-aware layers.

## Scheduling

`wwcx-nftables-live-state.timer` refreshes every 60 seconds. Network Defense orders after the Spamhaus, Fail2ban, and nftables observer oneshots.

## Accepted deployment

Implementation merged through PR #124. The bounded installer was run successfully on Edge1 on 2026-07-30.

Evidence:

```text
/var/lib/wwcx-deployment-evidence/nftables-live-state/20260730T090522Z
/var/lib/wwcx-deployment-evidence/nftables-live-state/20260730T090522Z/acceptance-summary.json
```

Accepted Network Defense result:

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

The private observer snapshot immediately before the public refresh reported the same topology and 1,866,363,293 packets with 4,478,862,225,755 bytes. The public snapshot reported 1,866,364,147 packets and 4,478,865,062,835 bytes moments later because live counters continued to advance.

The accepted state does not add a general firewall enforcement claim. The verified-enforcement count remains one from the separate Spamhaus verifier.

The installer made no nftables, firewall, DNS, routing, Fail2ban, proxy, IDS, authentication, or traffic-control change.

## Repository audit note

Before the feature branch was created, connector misuse briefly created a one-byte placeholder on `main` in commit `f954e3395dbecf36cad9dc209cf378eb2dcc986d`. It was removed immediately by commit `7b79f564f11928a63d5b028ab1e2fe0a61f65e6a` before implementation began. No runtime, deployment, or production system was affected.

## Safety boundary

This phase made no nftables or firewall mutation, service reload/restart, DNS/resolver/RPZ change, routing, Fail2ban, proxy, IDS, reputation-list, authentication, or traffic-control change. Any future control change requires separate explicit authorization and rollback/validation planning.
