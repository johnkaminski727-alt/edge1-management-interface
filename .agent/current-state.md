# Current State

Last verified: 2026-07-30  
Repository: `johnkaminski727-alt/edge1-management-interface`  
Authoritative branch: `main`  
Accepted Edge1 live revision: `a06f035e7fcf933a03ec752c66ce0261c5a65ba7`  
Latest completed repository merge: `0a09c8894ed6669e3a7fdf15b3f173bdbfa2caa7`  
Active repository branch: `design/edge1-authenticated-ops-browser-session-20260730`

## Verified live baseline

- Security Correlation and Network Defense are live and accepted.
- Suricata drill-down, caching, normalization, and enrichment are live.
- Spamhaus, Fail2ban, and nftables report accepted truthful states.
- Network Defense applies the accepted network-source freshness threshold of `600` seconds.
- DNS remains `not_staged`; DNS enforcement is false.
- Verified enforcement count remained `1` before and after freshness activation.
- Traffic controls and Network Defense timer state remained unchanged.

Protected live evidence:

```text
/var/lib/wwcx-deployment-evidence/edge1-project-completion-preflight/20260730T193415Z
/var/lib/wwcx-deployment-evidence/network-defense-freshness/20260730T195031Z
```

## Completed repository programs

- Protected Suricata retention runtime and closeout merged through PRs #138 and #139.
- Minimized public-summary route and strict CSP corrections merged through PRs #140 and #141.
- Disabled public-summary staging runtime and closeout merged through PRs #144 and #145; authoritative repository closeout is `0a09c8894ed6669e3a7fdf15b3f173bdbfa2caa7`.

## Authenticated detailed-operations boundary phase

A repository-only design is in progress on `design/edge1-authenticated-ops-browser-session-20260730`.

Implemented:

- disabled `/edge1-ops/` browser/session policy and critical JSON schema;
- OpenID Connect authorization-code plus PKCE design with external provider and secret paths;
- server-side opaque-session, secure cookie, idle/absolute timeout, rotation, and logout requirements;
- exact registered route and scope matrix;
- pure fail-closed path, identity, authorization, rate-limit, and redacted-audit evaluator;
- explicit 404, 401, 403, 405, and 429 contracts;
- strict restricted-response headers and no-CORS policy;
- credential-free Apache `.design` file with unconditional deny gates;
- policy drift, path ambiguity, session, scope, audit privacy, and static boundary tests;
- architecture and audit register.

The committed policy remains `design_only`, disabled, deployment unauthorized, authentication-change unauthorized, live-route unauthorized, provider unselected, and Apache adapter unverified.

No provider, client identifier, client secret, token, cookie, session store, audit file, listener, Apache include, route, authentication rule, user/group, or `/var/www` file has been created or changed.

Exact-head CI and final PR review are pending.

## Remaining separately authorized programs

- complete exact-head validation and merge for the repository-only authenticated boundary design;
- fresh authenticated Edge1 Apache, route, module, filesystem, listener, provider, session-store, audit, and rate-limit inventory;
- separately authorized provider/session implementation and restricted-route staging;
- separately authorized public-summary staging installation;
- separately authorized public cutover and detailed-artifact removal;
- separately authorized protected-retention installation and live acceptance.

## Safety boundary

No DNS, Unbound, RPZ, nftables rules, firewall, Fail2ban enforcement, routing, proxying, IDS rules, reputation lists, authentication, certificates, listeners, public or restricted routes, production traffic, timer scheduling, `/var/www` publication, release pruning, or data deletion changed.
