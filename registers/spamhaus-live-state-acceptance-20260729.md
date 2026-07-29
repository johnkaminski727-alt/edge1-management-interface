# Spamhaus Live-State Acceptance Record

Date: 2026-07-29
System: Edge1 / WW.CX Network Defense
Classification: internal, sanitized

## Deployment result

The checked-in installer completed successfully on Edge1 after the case-insensitive wording-validation correction merged through PR #119.

Reported terminal result:

```text
Spamhaus live-state observability deployment passed.
Live URL: http://127.0.0.1/edge1-status/network-defense/
Evidence: /var/lib/wwcx-deployment-evidence/spamhaus-live-state/20260729T180755Z
The verifier made no nftables, firewall, DNS, routing, Fail2ban, proxy, or traffic-control changes.
```

Authoritative evidence directory:

```text
/var/lib/wwcx-deployment-evidence/spamhaus-live-state/20260729T180755Z
```

## Verified facts

- deployment completed without rollback;
- the read-only verifier service and timer passed installer acceptance;
- Network Defense consumed the verifier snapshot consistently;
- `traffic_controls_changed` remained false;
- DNS enforcement remained disabled;
- no Spamhaus list refresh, filter reload, nftables mutation, firewall mutation, DNS, routing, Fail2ban, proxy, IDS, or authentication change was performed.

## Exact-state evidence gap

The final terminal excerpt did not include the JSON summaries printed earlier in the installer run. Therefore the exact accepted Spamhaus state is not copied into this repository record yet.

It must be read from:

```text
/var/lib/wwcx-deployment-evidence/spamhaus-live-state/20260729T180755Z/acceptance-summary.json
```

Allowed truthful states are:

- `active_verified`;
- `partial`;
- `not_present`;
- `unavailable`.

Do not infer `active_verified` solely from the generic deployment-passed line. The installer intentionally accepts truthful degraded states while preventing false enforcement claims.
