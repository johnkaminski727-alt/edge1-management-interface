# Spamhaus Live-State Verifier

Date: 2026-07-29
System: Edge1 / WW.CX Network Defense
Status: implementation merged and live installer acceptance passed

## Objective

Distinguish Spamhaus feed readiness from observed live nftables enforcement without modifying the Spamhaus table, sets, rules, updater, timer, or any other traffic control.

The Network Defense exporter reads bounded feed counters from:

```text
/var/lib/bigbird-networking/spamhaus/summary.txt
```

Those counters prove list preparation, while the dedicated verifier checks the live owned table and updater posture.

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

It publishes only bounded counts and booleans for table, sets, chains, rules, updater result, timer state, and enforcement verification. It does not publish addresses, set elements, the full ruleset, raw command output, payloads, credentials, or private keys.

## Verification criteria

`active_verified` requires all applicable checks:

1. `inet bigbird_spamhaus` is present;
2. `drop4` exists and is populated;
3. input and forward chains exist;
4. both chains contain a drop rule referencing `@drop4`;
5. if `drop6` is populated, both chains contain a drop rule referencing `@drop6`;
6. the updater service reports success and exit status zero;
7. the updater timer is active and enabled;
8. the snapshot is fresh, read-only, and reports `traffic_controls_changed: false`.

Incomplete evidence is represented as `partial`, `not_present`, or `unavailable` rather than converted into a false enforcement claim.

## Capability boundary

Reading nftables state requires `CAP_NET_ADMIN`. That capability is granted only to `wwcx-spamhaus-live-state.service`. The verifier is a hardened oneshot restricted to AF_UNIX/AF_NETLINK and write access under `/var/lib/bigbird-networking/spamhaus`.

`wwcx-network-defense.service` remains capability-free and consumes only the sanitized snapshot.

## Live deployment

Implementation merged through PR #118. The first live attempt failed before mutation because a runtime UI wording assertion was case-sensitive; the installer restored saved verifier state and recorded rollback evidence.

The assertion repair merged through PR #119 and both required CI workflows passed. The corrected installer then completed successfully.

Successful evidence:

```text
/var/lib/wwcx-deployment-evidence/spamhaus-live-state/20260729T180755Z
```

Failed and rolled-back evidence:

```text
/var/lib/wwcx-deployment-evidence/spamhaus-live-state/20260729T180002Z
```

The successful terminal result confirmed that the verifier made no nftables, firewall, DNS, routing, Fail2ban, proxy, or traffic-control changes.

## Exact-state readback

The final terminal excerpt did not include the earlier JSON summaries. The exact accepted state must be read from:

```text
/var/lib/wwcx-deployment-evidence/spamhaus-live-state/20260729T180755Z/acceptance-summary.json
```

Do not infer `active_verified` from the generic deployment-passed line. The installer intentionally accepts truthful `active_verified`, `partial`, `not_present`, or `unavailable` results.

## Safety boundary

This feature does not run nftables add, delete, flush, insert, replace, or file-load commands. It does not start or reload the Spamhaus filter updater. It does not change DNS, firewall, Fail2ban, proxy, routing, IDS, authentication, reputation lists, or traffic controls.
