# Current State

Last verified: 2026-07-29
Repository: `johnkaminski727-alt/edge1-management-interface`
Authoritative branch: `main`
Authoritative commit: `9425d3fc4f3846948ec43590b1f4d15cfc313266`

## Verified live state

- Network Defense observability deployed successfully on Edge1.
- Successful evidence: `/var/lib/wwcx-deployment-evidence/network-defense/20260729T053355Z`.
- Network Defense runtime reported:
  - `overall_state: limited`;
  - `dns_policy_state: not_staged`;
  - `enforcement_enabled: false`;
  - `traffic_controls_changed: false`.
- The Network Defense timer and one-shot exporter passed installation checks.
- No resolver, DNS answer, firewall, proxy, routing, Fail2ban, or IDS controls were changed.

## Verified repository state

PR #102 merged the bounded Security Correlation deployment package into `main` at commit `9425d3fc4f3846948ec43590b1f4d15cfc313266`.

The package provides:

- scoped root-owned output at `/var/www/edge1-status/security/correlation/data/security-correlation.json`;
- empty service capability sets;
- compatibility read URL `/edge1-status/security-correlation.json`;
- repository validation, backup, rollback, failure diagnostics, HTTP checks, and evidence capture;
- durable deployment and security-observability register documentation.

Both required CI workflows passed on the exact PR head:

- Edge1 Operator Validation run `30425842455`;
- Validate repository run `30425842388`.

## Known live gap

The live Network Defense snapshot still reports Security Correlation as unavailable because the newly merged correlation service and timer have not yet been installed on Edge1.

The bounded operator command is:

```bash
cd /opt/edge1-management-interface
git pull --ff-only origin main
sudo bash ./deploy/install-security-correlation-observability.sh
```

## Safety boundary

DNS policy remains `not_staged`. Resolver enforcement and all network control changes remain deferred pending exact authorization and dedicated validation.
