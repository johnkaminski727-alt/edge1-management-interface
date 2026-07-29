# Current State

Last verified: 2026-07-29
Repository: `johnkaminski727-alt/edge1-management-interface`
Authoritative branch: `main`
Authoritative commit before this domain-acceptance reconciliation: `cebc840152aa798f0a34d93d1708fa16add716b7`

## Verified live state

- Network Defense observability deployed successfully on Edge1.
- Network Defense evidence: `/var/lib/wwcx-deployment-evidence/network-defense/20260729T060015Z`.
- Security Correlation observability deployed successfully.
- Security Correlation evidence: `/var/lib/wwcx-deployment-evidence/security-correlation/20260729T061441Z`.
- Sanitized Security Controls inspection completed successfully.
- Security Controls evidence: `/var/lib/wwcx-deployment-evidence/security-controls-inspection/20260729T061447Z`.
- The initial acceptance attempt ran before Network Defense consumed the new correlation snapshot and failed safely.
- Initial acceptance timing evidence: `/var/lib/wwcx-deployment-evidence/security-observability-acceptance/20260729T061449Z`.
- The read-only acceptance verifier passed after the scheduled Network Defense refresh.
- Successful acceptance evidence: `/var/lib/wwcx-deployment-evidence/security-observability-acceptance/20260729T061936Z`.
- Final observability acceptance summary:
  - `verified_at: 2026-07-29T06:19:36.959113+00:00`;
  - `read_only: true`;
  - `traffic_controls_changed: false`;
  - Correlation age 51 seconds, 42 events, 0 correlations, and 4 of 4 sources available;
  - Network Defense age 15 seconds, overall state `limited`, and 5 of 6 sources available;
  - Correlation source age within Network Defense: 35 seconds;
  - `dns_policy_state: not_staged`;
  - `enforcement_enabled: false`.
- Security Correlation is live and consumed by Network Defense.
- Both firewall and Fail2ban posture were readable through the bounded inspector.

## Verified domain exposure

- `edge1.ww.cx` resolved on Edge1 to `89.147.109.253`.
- Apache reported the `edge1.ww.cx` name-based virtual host on ports 80 and 443.
- HTTP redirected to `https://edge1.ww.cx/edge1-status/`.
- The installed Let's Encrypt certificate covered `edge1.ww.cx`, `pbx.ww.cx`, and `sip.ww.cx` and was valid through 2026-10-17 01:27:37 UTC at verification time.
- The following HTTPS pages passed content checks:
  - `https://edge1.ww.cx/edge1-status/`;
  - `https://edge1.ww.cx/edge1-status/security/`;
  - `https://edge1.ww.cx/edge1-status/security/correlation.html`;
  - `https://edge1.ww.cx/edge1-status/network-defense/`.
- The Security Operations, Security Correlation, and Network Defense JSON feeds loaded successfully through the domain.
- Domain-resolved HTTPS returned HTTP 200 from remote address `89.147.109.253` with TLS verification result `0`.
- Domain acceptance evidence: `/var/lib/wwcx-deployment-evidence/edge1-status-domain/20260729T064854Z`.
- Sanitized domain acceptance snapshot:
  - Security Correlation was read-only with 32 events, 0 correlations, and 4 of 4 sources available;
  - Network Defense remained `limited` with 5 of 6 sources available;
  - DNS policy remained `not_staged`;
  - DNS enforcement remained disabled;
  - `traffic_controls_changed: false`.
- No DNS, firewall, routing, IDS, Fail2ban, proxy, resolver, or enforcement controls were changed during domain acceptance.

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
4. **Final observability records** — PR #109, merge commit `cebc840152aa798f0a34d93d1708fa16add716b7`.
   - closes the bounded deployment, inspection, and live acceptance sequence;
   - records the successful acceptance evidence and final sanitized summary.

Required CI passed on each exact implementation and evidence head before merge.

## Completion status

The bounded Security observability deployment, inspection, live acceptance, and `edge1.ww.cx` HTTPS domain acceptance are complete. No further authenticated Edge1 action is required for this phase.

Evidence-driven enhancements remain optional follow-up work and must preserve the established privacy, least-privilege, rollback, and no-traffic-change boundaries.

## Safety boundary

DNS policy remains `not_staged`. Resolver enforcement and all firewall, Fail2ban, proxy, routing, IDS, reputation-filter, authentication-boundary, or other network control changes remain deferred pending exact authorization and dedicated validation.
