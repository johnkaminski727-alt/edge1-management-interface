# Current State

Last verified: 2026-07-30  
Repository: `johnkaminski727-alt/edge1-management-interface`  
Authoritative branch: `main`  
Accepted Edge1 live revision: `a06f035e7fcf933a03ec752c66ce0261c5a65ba7`  
Latest completed repository closeout: `a8af7fa77d9eb81ecd69d22e9d314de478975d66`  
Active repository branch: `design/edge1-restricted-artifact-migration-manifest-20260730`

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
- Disabled public-summary staging runtime and closeout merged through PRs #144 and #145.
- Authenticated detailed-operations browser/session boundary and closeout merged through PRs #146 and #147; authoritative closeout is `a8af7fa77d9eb81ecd69d22e9d314de478975d66`.

## Restricted artifact migration manifest phase

A repository-only, read-only migration design is in progress on `design/edge1-restricted-artifact-migration-manifest-20260730`.

Implemented:

- disabled source-to-target migration manifest for `/var/www/edge1-status` to future `/var/lib/wwcx-edge1-ops/releases` staging;
- 23 exact repository-declared artifacts and five live-enumerated prefix groups;
- exact target-route and scope validation against the authenticated `/edge1-ops/` policy;
- read-only SHA-256 inventory-record validation;
- exact and prefix mapping with preserved evidence metadata;
- unknown-artifact `preserve_review`, missing-known reporting, and duplicate-target blocking;
- separate staging and cutover readiness results that remain false under the committed policy;
- tests covering repository-reference coverage, safe paths, inventory metadata, unknown preservation, collision handling, and absence of mutation operations;
- architecture and audit register.

Committed gates remain `design_only`, disabled, staging unauthorized, cutover unauthorized, deletion unauthorized, and source mutation forbidden.

No live Edge1 filesystem was inspected. No source file was opened, hashed, copied, moved, renamed, modified, removed, or routed. Exact-head CI and final PR review are pending.

## Remaining separately authorized programs

- complete exact-head validation and merge for the repository-only migration manifest;
- fresh authenticated Edge1 Apache, route, filesystem, publisher, service, listener, hash, backup, provider, session-store, audit, and rate-limit inventory;
- separately authorized restricted release staging and authenticated route implementation;
- separately authorized public-summary staging installation;
- separately authorized public cutover and detailed-artifact removal;
- separately authorized protected-retention installation and live acceptance.

## Safety boundary

No DNS, Unbound, RPZ, nftables rules, firewall, Fail2ban enforcement, routing, proxying, IDS rules, reputation lists, authentication, certificates, listeners, public or restricted routes, production traffic, timer scheduling, `/var/www` publication or removal, release creation, pruning, or data deletion changed.
