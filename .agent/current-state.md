# Current State

Last verified: 2026-07-30  
Repository: `johnkaminski727-alt/edge1-management-interface`  
Authoritative branch: `main`  
Accepted Edge1 live revision: `a06f035e7fcf933a03ec752c66ce0261c5a65ba7`  
Protected-retention repository merge: `98d4d2bb2b3f57b54f3ca6f1779ec9fd2d4ab694`

## Verified live baseline

- Security Correlation and Network Defense are live and accepted.
- Suricata drill-down, caching, normalization, and enrichment are live.
- Spamhaus, Fail2ban, and nftables report accepted truthful states.
- Network Defense applies the accepted network-source freshness threshold of `600` seconds.
- DNS remains `not_staged`; DNS enforcement is false.
- Verified enforcement count remained `1` before and after freshness activation.
- Traffic controls and Network Defense timer state remained unchanged.

## Live completion evidence

Read-only completion preflight:

```text
/var/lib/wwcx-deployment-evidence/edge1-project-completion-preflight/20260730T193415Z
```

Bounded freshness activation:

```text
/var/lib/wwcx-deployment-evidence/network-defense-freshness/20260730T195031Z
```

The Network Defense freshness project is complete and accepted at live revision `a06f035e7fcf933a03ec752c66ce0261c5a65ba7`.

## Protected Suricata retention runtime phase

The repository-only implementation is complete and merged through PR #138 as `98d4d2bb2b3f57b54f3ca6f1779ec9fd2d4ab694`.

Implemented:

- `server/suricata_protected_retention.py` for sanitized source validation, deterministic SHA-256 deduplication, bounded SQLite retention, age/count/page pruning, atomic root-only status, and bounded read-only local queries;
- `deploy/systemd/wwcx-suricata-protected-retention.service` with AF_UNIX-only, empty-capability, strict filesystem sandboxing;
- `deploy/systemd/wwcx-suricata-protected-retention.timer` with a proposed 120-second interval;
- `tests/test_suricata_protected_retention.py` using temporary files and databases;
- `registers/suricata-protected-retention-runtime-register-20260730.md`.

Exact-head validation for `f1a619479b9d407e83b44caa306e836c282b3b77` passed:

- `Validate repository` run 640;
- `Edge1 Operator Validation` run 472.

The branch was zero commits behind `main`, mergeable, and had no review threads before merge.

The authoritative committed policy remains `design_only`, `enabled: false`, and `deployment_authorized: false`. No installer or live activation is included. No Edge1 database, unit, timer, listener, route, or public artifact has been created or changed.

## Remaining separately authorized programs

- separately design and authorize any Edge1 installer and live acceptance for protected retention;
- minimized public-summary server-side publication;
- authenticated detailed-operations browser/session boundary;
- staged public-boundary cutover and detailed-artifact removal.

## Safety boundary

No DNS, Unbound, RPZ, nftables rules, firewall, Fail2ban enforcement, routing, proxying, IDS rules, reputation lists, authentication, certificates, listeners, public routes, production traffic, or timer scheduling changed. Production history ingestion, data deletion, `/var/www` publication, and detailed-artifact removal remain unauthorized.
