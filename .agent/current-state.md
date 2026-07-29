# Current State

Last verified: 2026-07-29
Repository: `johnkaminski727-alt/edge1-management-interface`
Authoritative branch: `main`
Authoritative commit before this evidence reconciliation: `922e5035d5af22a99e5035b60dfc779c4ae95275`

## Verified live state

- Network Defense observability deployed successfully on Edge1.
- Successful evidence: `/var/lib/wwcx-deployment-evidence/network-defense/20260729T060015Z`.
- Network Defense runtime reported:
  - `overall_state: limited`;
  - `dns_policy_state: not_staged`;
  - `enforcement_enabled: false`;
  - `traffic_controls_changed: false`.
- The Network Defense timer and one-shot exporter passed installation checks.
- No resolver, DNS answer, firewall, proxy, routing, Fail2ban, or IDS controls were changed.

## Verified repository state

The complete bounded Security observability continuation package is merged into `main`:

1. **Security Correlation deployment** — PR #102, commit `9425d3fc4f3846948ec43590b1f4d15cfc313266`.
   - scoped root-owned output;
   - hardened service and one-minute timer;
   - compatibility read endpoint;
   - validation, backup, rollback, diagnostics, HTTP checks, and evidence capture.
2. **Security Controls inspection** — PR #104, commit `7b75ac6ae3047e39b3b5395b904eb19071920d3c`.
   - sanitized read-only nftables aggregate counts;
   - sanitized Fail2ban jail names and numeric counters;
   - no raw rules, addresses, ports, payloads, banned-IP lists, or raw command output;
   - no permanent service or control change.
3. **Security observability acceptance** — PR #105, commit `ac35bc4667222017d946408144a56a60e6c43e60`.
   - proves correlation service/timer health and freshness;
   - proves Network Defense consumed the correlation source;
   - verifies DNS enforcement remains disabled and traffic controls remain unchanged;
   - captures protected acceptance or failure evidence.

Required CI passed on each exact merged head:

- PR #102: Edge1 Operator Validation `30425842455`; Validate repository `30425842388`.
- PR #104: Edge1 Operator Validation `30426203898`; Validate repository `30426203900`.
- PR #105: Edge1 Operator Validation `30426363318`; Validate repository `30426363513`.

## Remaining live sequence

The repository work is complete. The remaining steps require the existing authenticated Edge1 SSH session:

```bash
cd /opt/edge1-management-interface
git pull --ff-only origin main
sudo bash ./deploy/install-security-correlation-observability.sh
sudo bash ./tools/security/inspect-security-controls.sh
sudo bash ./tools/security/verify-security-observability-live.sh
```

The acceptance verifier may report that Network Defense has not consumed correlation yet if its next scheduled refresh has not occurred. That result is read-only and preserves evidence; rerun the same verifier after the next timer refresh rather than restarting or changing controls.

## Safety boundary

DNS policy remains `not_staged`. Resolver enforcement and all firewall, Fail2ban, proxy, routing, IDS, or other network control changes remain deferred pending exact authorization and dedicated validation.
