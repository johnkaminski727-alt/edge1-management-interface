# Security Observability and nftables Aggregate Handoff

Date: 2026-07-30  
Repository: `johnkaminski727-alt/edge1-management-interface`  
Authoritative branch: `main`  
Current branch: `feature/nftables-aggregate-observability-20260730`  
Latest live closeout merge: `1ea802effb166ced18c3e1e4675419349aa647eb`

## Completed live work

- Network Defense and Security Correlation deployed and accepted.
- `edge1.ww.cx` HTTPS status pages and JSON feeds accepted.
- Accessible Suricata drill-down, last-known-good cache, normalized schema, and source collector enrichment deployed.
- Spamhaus live-state accepted as `active_verified` and remains the sole verified enforcement source.
- Fail2ban live-state accepted as `active_observed` with service/socket health and all 7 reported jails observed.
- Network Defense remains `limited`, DNS remains unstaged, and traffic controls remain unchanged.

## Live URLs

```text
https://edge1.ww.cx/edge1-status/
https://edge1.ww.cx/edge1-status/security/
https://edge1.ww.cx/edge1-status/security/correlation.html
https://edge1.ww.cx/edge1-status/network-defense/
```

## Authoritative live evidence

```text
/var/lib/wwcx-deployment-evidence/security-observability-acceptance/20260729T061936Z
/var/lib/wwcx-deployment-evidence/edge1-status-domain/20260729T064854Z
/var/lib/wwcx-deployment-evidence/suricata-alert-normalization/20260729T082557Z
/var/lib/wwcx-deployment-evidence/suricata-collector-enrichment/20260729T165711Z
/var/lib/wwcx-deployment-evidence/spamhaus-live-state/20260729T180755Z
/var/lib/wwcx-deployment-evidence/spamhaus-live-state/20260729T180755Z/acceptance-summary.json
/var/lib/wwcx-deployment-evidence/fail2ban-live-state/20260730T004144Z
/var/lib/wwcx-deployment-evidence/fail2ban-live-state/20260730T004144Z/acceptance-summary.json
```

## Current bounded implementation

Objective:

Publish sanitized general nftables topology and counter aggregates without changing nftables or claiming general firewall enforcement.

Implemented:

- contract `wwcx.nftables-aggregate-live-state.v1`;
- read-only `nft -j list ruleset` inspection;
- read-only `systemctl show nftables.service` inspection;
- aggregate object, family, hook, policy, verdict, element, packet, and byte counts;
- strict exclusion of all names, addresses, ports, interfaces, elements, expressions, comments, handles, priorities, jump targets, raw output, credentials, and private keys;
- private mode-`0640` snapshot under a mode-`0750` directory;
- public aggregate-only final Network Defense wrapper layered over DNS, Spamhaus, and Fail2ban;
- `enforcement_verified: false` and `traffic_controls_changed: false` in every state;
- truthful `ruleset_observed`, `partial`, `empty`, `not_installed`, and `unavailable` states;
- hardened root oneshot with only `CAP_NET_ADMIN` and `AF_UNIX AF_NETLINK`;
- 60-second timer and capability-free Network Defense ordering;
- rollback-safe installer and evidence capture;
- parser, privacy, stale-state, integration, runtime-wiring, deployment-safety, and legacy compatibility tests;
- architecture document and implementation register.

## Remaining gate

1. Open the nftables aggregate observability PR.
2. Require Edge1 Operator Validation and full repository validation on the exact head.
3. Merge only if scope, review state, and both checks pass.
4. On Edge1 run:

```bash
cd /opt/edge1-management-interface
git pull --ff-only origin main
sudo bash ./deploy/install-nftables-live-state-observability.sh
```

5. Record the truthful live state and evidence root:

```text
/var/lib/wwcx-deployment-evidence/nftables-live-state/<timestamp>
```

A degraded state is acceptable evidence. Do not reload, restart, repair, or otherwise mutate nftables to improve the result.

## Repository audit note

Commit `f954e3395dbecf36cad9dc209cf378eb2dcc986d` accidentally created a one-byte verifier placeholder on `main`; commit `7b79f564f11928a63d5b028ab1e2fe0a61f65e6a` removed it immediately before the branch was created. No runtime or production system was affected.

## Safety boundary

No nftables or firewall mutation, service reload/restart, Fail2ban jail/action mutation, Unbound or RPZ change, DNS-answer change, proxy, routing, IDS-rule, reputation-list, authentication, or traffic-cutover change is included. Public status exposes only sanitized aggregates and no ruleset names, addresses, elements, expressions, comments, handles, raw output, credentials, or private keys.
