# Security Observability, Suricata Enrichment, and Spamhaus Verifier Handoff

Date: 2026-07-29
Repository: `johnkaminski727-alt/edge1-management-interface`
Authoritative branch: `main`
Latest live collector-enrichment merge: `21b87664355e5f83173a630f24276389a6dcbbf6`
Latest synchronized reporting fix: `bb293f15da214d600abae823e4db17680eac036c`

## Completed live work

- Network Defense bounded deployment completed.
- Security Correlation bounded deployment completed.
- Read-only Security observability acceptance passed.
- `edge1.ww.cx` HTTPS domain acceptance passed.
- Accessible Suricata alert drill-down deployed.
- Edge1 last-known-good Security Operations cache deployed and verified.
- Nested Suricata alert normalization deployed.
- Source-controlled Big Bird collector enrichment merged through PR #115 and activated on Edge1.
- Security Operations, Correlation, and Network Defense were refreshed and accepted after collector activation.
- The exposed `wwadmin` credential was rotated and shell history was cleared.

## Live URLs

```text
https://edge1.ww.cx/edge1-status/
https://edge1.ww.cx/edge1-status/security/
https://edge1.ww.cx/edge1-status/security/correlation.html
https://edge1.ww.cx/edge1-status/network-defense/
```

## Authoritative evidence

```text
Base Security observability acceptance:
/var/lib/wwcx-deployment-evidence/security-observability-acceptance/20260729T061936Z

edge1.ww.cx domain acceptance:
/var/lib/wwcx-deployment-evidence/edge1-status-domain/20260729T064854Z

Suricata normalization activation:
/var/lib/wwcx-deployment-evidence/suricata-alert-normalization/20260729T082557Z

Suricata collector enrichment:
/var/lib/wwcx-deployment-evidence/suricata-collector-enrichment/20260729T165711Z
```

## Final live collector result

```json
{
  "ok": true,
  "alert_count": 22,
  "source_port_count": 22,
  "destination_port_count": 22,
  "application_protocol_count": 22,
  "signature_id_count": 22,
  "generator_id_count": 22,
  "revision_count": 22,
  "flow_id_count": 22,
  "correlation_events": 22,
  "correlations": 0,
  "network_defense_state": "limited",
  "traffic_controls_changed": false
}
```

The normalized public feed also verified 22 classified alerts, 22 known risks, live non-stale cache, schema `2.0`, alert schema `wwcx.suricata-alert.v1`, read-only correlation, DNS policy `not_staged`, and disabled DNS enforcement.

## Current implementation awaiting merge and activation

Branch:

```text
feature/spamhaus-live-state-verifier-20260729
```

Objective:

Distinguish Spamhaus feed readiness from observed live enforcement without changing the filter.

Implemented:

- `server/spamhaus_live_state_verifier.py`;
- contract `wwcx.spamhaus-live-state.v1`;
- read-only `nft -j list table inet bigbird_spamhaus` inspection;
- updater service result and timer-state inspection;
- bounded counts and booleans only;
- exclusion of addresses, set elements, full ruleset, and raw command output;
- hardened verifier service and one-minute timer;
- `CAP_NET_ADMIN` confined to the verifier service;
- capability-free Network Defense consumer;
- Network Defense state transition to `active_verified` only on complete fresh evidence;
- rollback-safe installer and evidence capture;
- parser, privacy, command-safety, integration, runtime-wiring, and deployment validation;
- implementation document and register.

Planned activation after merge:

```bash
cd /opt/edge1-management-interface
git pull --ff-only origin main
sudo bash ./deploy/install-spamhaus-live-state-observability.sh
```

Expected evidence:

```text
/var/lib/wwcx-deployment-evidence/spamhaus-live-state/<timestamp>
```

The installer accepts a truthful `active_verified`, `partial`, `not_present`, or `unavailable` state. It must not convert incomplete evidence into an enforcement claim.

## Remaining gate

1. Open the verifier PR.
2. Require Edge1 Operator Validation and full repository validation on the exact head.
3. Merge only if the scope and checks pass.
4. Run the checked-in installer on Edge1.
5. Record the live verifier state and Network Defense acceptance.

## Safety boundary

Not included:

- Spamhaus list refresh or filter reload;
- nftables add, delete, flush, insert, replace, or file-load operations;
- Unbound or resolver configuration changes;
- RPZ staging or activation;
- DNS answer changes;
- general firewall or Fail2ban mutations;
- proxy, routing, IDS rule, reputation-list, authentication, or traffic-cutover changes;
- address, set-element, full-ruleset, payload, packet-body, or raw-log publication;
- claims of active enforcement without direct live-state evidence.
