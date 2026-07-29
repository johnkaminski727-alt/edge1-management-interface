# Spamhaus Live-State Verifier

Date: 2026-07-29
System: Edge1 / WW.CX Network Defense
Status: implemented on feature branch; live activation pending merge

## Objective

Distinguish Spamhaus feed readiness from observed live nftables enforcement without modifying the Spamhaus table, sets, rules, updater, timer, or any other traffic control.

The existing Network Defense exporter reads bounded feed counters from:

```text
/var/lib/bigbird-networking/spamhaus/summary.txt
```

Those counters prove that lists were prepared, but do not prove that the expected nftables table and hooked drop rules remain loaded.

## Verifier contract

Authoritative implementation:

```text
server/spamhaus_live_state_verifier.py
```

Published snapshot:

```text
/var/lib/bigbird-networking/spamhaus/live-state.json
```

Contract:

```text
wwcx.spamhaus-live-state.v1
```

The verifier executes only:

```text
nft -j list table inet bigbird_spamhaus
systemctl show bigbird-spamhaus-filter.service ...
systemctl is-active bigbird-spamhaus-filter.timer
systemctl is-enabled bigbird-spamhaus-filter.timer
```

It publishes only bounded counts and booleans:

- expected table present;
- `drop4` and `drop6` set presence and element counts;
- input and forward chain presence, hook, policy, and priority;
- IPv4 and IPv6 drop-rule counts by chain;
- updater service result and exit status;
- timer active and enabled state;
- IPv4, IPv6, and complete enforcement verification status.

It does not publish:

- network addresses or set elements;
- the full nftables ruleset;
- raw command output;
- packet payloads or raw logs;
- credentials or private keys.

## Verification criteria

`active_verified` requires all applicable checks:

1. `inet bigbird_spamhaus` is present;
2. `drop4` exists and contains at least one element;
3. input and forward chains exist;
4. both chains contain a drop rule referencing `@drop4`;
5. if `drop6` is populated, both chains contain a drop rule referencing `@drop6`;
6. `bigbird-spamhaus-filter.service` reports `Result=success` and `ExecMainStatus=0`;
7. `bigbird-spamhaus-filter.timer` is active and enabled;
8. the snapshot remains read-only with `traffic_controls_changed: false`.

Missing or incomplete evidence is represented as `partial`, `not_present`, or `unavailable`. It is not converted into a false claim of enforcement.

## Capability boundary

Reading nftables state requires `CAP_NET_ADMIN`. That capability is granted only to:

```text
wwcx-spamhaus-live-state.service
```

The service is a root-owned oneshot with:

- `NoNewPrivileges=true`;
- `ProtectSystem=strict`;
- `ProtectHome=true`;
- kernel, module, control-group, SUID/SGID, personality, and executable-memory protections;
- address families restricted to `AF_UNIX` and `AF_NETLINK`;
- write access limited to `/var/lib/bigbird-networking/spamhaus`;
- capability bounding and ambient sets limited to `CAP_NET_ADMIN`.

`wwcx-network-defense.service` remains capability-free and reads only the sanitized verifier snapshot.

## Scheduling and integration

The verifier timer refreshes every minute. Network Defense also `Wants` and orders itself after the verifier oneshot, ensuring a manual or scheduled Network Defense refresh attempts to update live-state evidence first.

When the verifier is fresh and complete, the Network Defense component changes from:

```text
feed_ready
```

to:

```text
active_verified
```

The top-level verified-enforcement count then includes the dedicated Spamhaus verifier. DNS, general firewall, Fail2ban, and proxy enforcement remain separate and unverified.

## Activation

After merge:

```bash
cd /opt/edge1-management-interface
git pull --ff-only origin main
sudo bash ./deploy/install-spamhaus-live-state-observability.sh
```

Evidence root:

```text
/var/lib/wwcx-deployment-evidence/spamhaus-live-state/<timestamp>
```

The installer validates code, backs up affected units and snapshots, installs the verifier service/timer, refreshes Network Defense, verifies the HTTPS page and safety contracts, and restores the previous observability files on failure.

## Safety boundary

This feature does not run nftables add, delete, flush, insert, replace, or file-load commands. It does not start or reload the Spamhaus filter updater. It does not change DNS, firewall, Fail2ban, proxy, routing, IDS, authentication, reputation lists, or traffic controls.
