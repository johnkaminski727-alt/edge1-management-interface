# nftables Aggregate Live-State Observability

Date: 2026-07-30  
System: Edge1 / WW.CX Network Defense  
Status: implemented; live activation pending merge

## Objective

Publish bounded current topology and counter aggregates for the live Edge1 nftables ruleset without changing nftables, firewall policy, sets, rules, chains, DNS, routing, Fail2ban, proxy, IDS, authentication, or traffic controls.

The existing Network Defense firewall card used normalized event counts only. It could not distinguish absent event telemetry from a present live ruleset or show bounded object, hook, policy, verdict, and counter totals.

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

- table, chain, set, map, counter, or flowtable names;
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

## Deployment

After merge:

```bash
cd /opt/edge1-management-interface
git pull --ff-only origin main
sudo bash ./deploy/install-nftables-live-state-observability.sh
```

Expected evidence root:

```text
/var/lib/wwcx-deployment-evidence/nftables-live-state/<timestamp>
```

The installer validates the complete layered exporter path, backs up affected observability units and snapshots, installs only the new observer units and updated Network Defense unit, captures acceptance evidence, and restores prior observability state on failure. A degraded observation state is acceptable and does not trigger any firewall repair or reload.

## Repository audit note

Before the feature branch was created, connector misuse briefly created a one-byte placeholder on `main` in commit `f954e3395dbecf36cad9dc209cf378eb2dcc986d`. It was removed immediately by commit `7b79f564f11928a63d5b028ab1e2fe0a61f65e6a` before implementation began. No runtime, deployment, or production system was affected.

## Safety boundary

This phase makes no nftables or firewall mutation, service reload/restart, DNS/resolver/RPZ change, routing, Fail2ban, proxy, IDS, reputation-list, authentication, or traffic-control change. Any future control change requires separate explicit authorization and rollback/validation planning.
