# Edge1 Status Domain Acceptance Register

Date: 2026-07-29
Classification: internal, sanitized
System: Edge1 / WW.CX Operations Center
Domain: `edge1.ww.cx`

## Purpose

Record the authoritative HTTPS domain acceptance result for the Edge1 Operations Center and its Security Operations, Security Correlation, and Network Defense modules.

## Authoritative evidence

```text
/var/lib/wwcx-deployment-evidence/edge1-status-domain/20260729T064854Z
```

The evidence directory remains on Edge1 and contains the operator-run preflight, TLS inspection, HTML content checks, live JSON snapshots, sanitized acceptance summary, and completion marker. Raw live JSON is not committed to the repository.

## Verified domain posture

- `edge1.ww.cx` resolved on Edge1 to `89.147.109.253`.
- Apache configuration syntax passed.
- Apache reported the `edge1.ww.cx` name-based virtual host on ports 80 and 443.
- Port 80 redirected `/edge1-status/` to the HTTPS URL.
- Apache was listening on ports 80 and 443.
- The installed Let's Encrypt certificate:
  - subject: `CN = edge1.ww.cx`;
  - SANs: `edge1.ww.cx`, `pbx.ww.cx`, and `sip.ww.cx`;
  - valid from 2026-07-19 01:27:38 UTC;
  - valid through 2026-10-17 01:27:37 UTC.
- The final domain-resolved request returned HTTP 200 from `89.147.109.253` with TLS verification result `0`.

## Verified pages

All required HTTPS pages passed content checks:

| Module | URL | Result |
| --- | --- | --- |
| Operations Center | `https://edge1.ww.cx/edge1-status/` | PASS |
| Security Operations | `https://edge1.ww.cx/edge1-status/security/` | PASS |
| Security Correlation | `https://edge1.ww.cx/edge1-status/security/correlation.html` | PASS |
| Network Defense | `https://edge1.ww.cx/edge1-status/network-defense/` | PASS |

## Verified live feeds

The following JSON feeds loaded successfully through the real HTTPS domain:

```text
https://edge1.ww.cx/edge1-status/security-operations.json
https://edge1.ww.cx/edge1-status/security-correlation.json
https://edge1.ww.cx/edge1-status/network-defense/data/network-defense.json
```

Sanitized acceptance summary:

```json
{
  "ok": true,
  "host": "edge1.ww.cx",
  "operations_center": "available",
  "security_operations": "available",
  "security_correlation": "available",
  "network_defense": {
    "overall_state": "limited",
    "available_sources": 5,
    "source_count": 6,
    "dns_policy_state": "not_staged",
    "dns_enforcement_enabled": false
  },
  "correlation": {
    "read_only": true,
    "events": 32,
    "correlations": 0,
    "available_sources": 4,
    "source_count": 4
  },
  "traffic_controls_changed": false
}
```

The live Correlation event count changed from the earlier observability acceptance snapshot because the exporter continued to refresh. The source-availability, read-only, DNS-policy, and no-traffic-change contracts remained intact.

## Safety and change record

The domain acceptance run was read-only. It did not modify:

- DNS records or resolver configuration;
- Apache virtual hosts or aliases;
- TLS certificates;
- network listeners;
- firewall or nftables rules;
- Fail2ban jails;
- proxy, routing, IDS, or reputation-filter controls;
- DNS policy activation or enforcement;
- authentication or access-control boundaries.

Verified retained safety state:

```text
correlation.read_only: true
network_defense.dns_policy_state: not_staged
network_defense.dns_enforcement_enabled: false
traffic_controls_changed: false
```

## Completion status

The Edge1 Operations Center and the three security modules are available through the `edge1.ww.cx` HTTPS domain. The bounded domain acceptance is complete, and no corrective production change was required.

Any future change to public exposure, authentication, DNS, TLS, firewall, resolver, or traffic controls requires a separate bounded plan, rollback, and acceptance record.
