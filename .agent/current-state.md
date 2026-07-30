# Current State

Last verified: 2026-07-30 19:15 UTC  
Repository: `johnkaminski727-alt/edge1-management-interface`  
Authoritative branch: `main`  
Latest design merge: `6e0bbb9d38cd2b89a5ba59ced1534a93ba3aa2eb`  
Design PR: `#130`

## Verified live security observability

- Network Defense and Security Correlation are deployed and accepted through `edge1.ww.cx`.
- Security Operations includes accessible Suricata drill-down, last-known-good caching, normalization, and enriched allowlisted alert fields.
- Spamhaus is `active_verified` and remains the sole enforcement-verified source.
- Fail2ban is `active_observed` with service/socket health and 7 observed jails.
- General nftables aggregate visibility is `ruleset_observed`.
- Network Defense remains `limited`, 8 of 9 sources are available, DNS policy is `not_staged`, DNS enforcement is disabled, and traffic controls are unchanged.

## Completed repository phases

- Network Defense freshness: closed through PR #127; live activation unclaimed.
- Protected Suricata retention design: closed through PR #129; disabled and non-deploying.
- Edge1 public access boundary design: merged through PR #130 as `6e0bbb9d38cd2b89a5ba59ced1534a93ba3aa2eb`.

## Accepted public-boundary decision

The current `/edge1-status/` tree is a mixed boundary and should not remain unchanged as the long-term design.

Target:

- public: minimized landing page plus allowlist-only `/edge1-status/public/status.json`;
- restricted: separately authenticated, fail-closed detailed operations surface represented as `/edge1-ops/`;
- no anonymous fallback;
- detailed security, topology, Git/change, automation, incident, communications, financial, and report/evidence data restricted.

The policy remains `design_only`, `enabled: false`, and `deployment_authorized: false`.

## Validation

Exact design head: `24eacfa1388b9c3b9bafb1c8f880af1da3355aea`

- `Validate repository` run 618: success;
- `Edge1 Operator Validation` run 450: success;
- zero commits behind `main` before merge;
- no unresolved review threads;
- scope limited to policy, schema, design, register, static validation, and `.agent` records.

## Next safest repository phase

Build the minimized public summary schema, allowlist exporter, fixtures, and static landing page without routing or publishing them. No Apache, proxy, authentication, certificate, listener, DNS, `/var/www`, or production change is authorized.

## Live evidence gap

No authenticated Edge1 shell is available. Complete Apache authorization, aliases, headers, CORS, directory listing, and route inventory remain unverified.

## Safety boundary

No DNS, Unbound, RPZ, nftables, firewall, Fail2ban, routing, proxying, IDS, reputation lists, authentication, certificates, listeners, public access, published files, deletion, or production traffic is changed.
