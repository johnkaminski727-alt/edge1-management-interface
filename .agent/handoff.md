# Security Observability, Spamhaus, and Fail2ban Handoff

Date: 2026-07-29  
Repository: `johnkaminski727-alt/edge1-management-interface`  
Authoritative branch: `main`  
Latest completed closeout merge: `8f1319150e180fcf4b06bc30a122e4541f65fd02`

## Completed live work

- Network Defense and Security Correlation deployed and accepted.
- `edge1.ww.cx` HTTPS status pages and JSON feeds accepted.
- Accessible Suricata drill-down, last-known-good cache, normalized schema, and source collector enrichment deployed.
- The accepted collector run retained ports, application protocol, SID/GID/revision, and flow ID for all 22 observed alerts.
- Read-only Spamhaus live-state verifier deployed and directly accepted as `active_verified`.
- Spamhaus contributes one verified enforcement source; Network Defense remains `limited`, DNS remains unstaged, and traffic controls remain unchanged.

## Live URLs

```text
https://edge1.ww.cx/edge1-status/
https://edge1.ww.cx/edge1-status/security/
https://edge1.ww.cx/edge1-status/security/correlation.html
https://edge1.ww.cx/edge1-status/network-defense/
```

## Authoritative evidence

```text
Security observability:
/var/lib/wwcx-deployment-evidence/security-observability-acceptance/20260729T061936Z

edge1.ww.cx domain:
/var/lib/wwcx-deployment-evidence/edge1-status-domain/20260729T064854Z

Suricata normalization:
/var/lib/wwcx-deployment-evidence/suricata-alert-normalization/20260729T082557Z

Suricata collector enrichment:
/var/lib/wwcx-deployment-evidence/suricata-collector-enrichment/20260729T165711Z

Spamhaus live-state and exact summary:
/var/lib/wwcx-deployment-evidence/spamhaus-live-state/20260729T180755Z
/var/lib/wwcx-deployment-evidence/spamhaus-live-state/20260729T180755Z/acceptance-summary.json
```

## Current bounded implementation

Branch:

```text
feature/fail2ban-live-state-observability-20260729
```

Objective:

Publish Fail2ban service, local socket, and aggregate jail-health evidence without changing Fail2ban or claiming packet enforcement.

Implemented:

- contract `wwcx.fail2ban-live-state.v1`;
- read-only `systemctl show fail2ban.service` inspection;
- read-only `fail2ban-client status` and per-jail status inspection;
- jail-name sanitization and 64-jail bound;
- aggregate/per-jail currently and total failed/banned counters;
- banned-address, log-path, raw-output, command, credential, and private-key exclusion;
- private verifier snapshot at `/var/lib/bigbird-security/fail2ban/live-state.json`;
- public Network Defense aggregate-only wrapper;
- truthful `active_observed`, `partial`, `inactive`, `not_installed`, and `unavailable` states;
- `enforcement_verified: false` in every state;
- hardened root oneshot with no capabilities and AF_UNIX only;
- one-minute timer and capability-free Network Defense ordering;
- rollback-safe installer and acceptance evidence;
- parser, privacy, stale-state, integration, runtime-wiring, and deployment-safety tests;
- architecture document and register.

## Remaining gate

1. Open the Fail2ban observability PR.
2. Require Edge1 Operator Validation and full repository validation on the exact head.
3. Merge only if scope, review state, and both checks pass.
4. On Edge1 run:

```bash
cd /opt/edge1-management-interface
git pull --ff-only origin main
sudo bash ./deploy/install-fail2ban-live-state-observability.sh
```

5. Record the truthful live state and evidence root:

```text
/var/lib/wwcx-deployment-evidence/fail2ban-live-state/<timestamp>
```

A degraded state is acceptable evidence. Do not start or alter Fail2ban to improve the result.

## Safety boundary

No Fail2ban jail/action mutation, service start/stop/reload/restart, nftables or firewall mutation, Unbound or RPZ change, DNS-answer change, proxy, routing, IDS-rule, reputation-list, authentication, or traffic-cutover change is included. Public status exposes no jail records, banned addresses, log paths, raw client output, credentials, or private keys.
