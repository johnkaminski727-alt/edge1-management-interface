# Current State

Last verified: 2026-07-30  
Repository: `johnkaminski727-alt/edge1-management-interface`  
Authoritative branch: `main`  
Accepted Edge1 live revision: `a06f035e7fcf933a03ec752c66ce0261c5a65ba7`  
Current repository branch: `feature/edge1-public-summary-staging-runtime-20260730`

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

- Protected Suricata retention runtime merged through PR #138 as `98d4d2bb2b3f57b54f3ca6f1779ec9fd2d4ab694`; closeout merged through PR #139 as `4b14a3c513dd7878c0d8c2ee4fa751f292e7bb6a`.
- Minimized public-summary route correction merged through PR #140 as `4fc5d765805b86be8ddee58f08c2676116517cbb`.
- Strict CSP correction merged through PR #141 as `feb771b6ab53ed9547fec81dbaea964a0246f27d`.

The route is now consistently `/edge1-status/public/status.json`, and the page uses external same-origin CSS with the exact approved CSP and no `unsafe-inline` requirement.

## Public summary staging runtime phase

A repository-only implementation is in progress on `feature/edge1-public-summary-staging-runtime-20260730`.

Implemented:

- disabled staging policy and JSON schema;
- fail-closed release builder using only the three sanitized source snapshots;
- exact four-file public release allowlist;
- immutable release directories and atomic `current` symlink selection;
- SHA-256 metadata outside the public release with `0700`/`0600` protection;
- hardened proposed oneshot and 60-second timer;
- explicitly non-active Apache alias/header proposal;
- temporary-directory functional, privacy, permissions, systemd, and Apache contract tests;
- architecture and audit register.

The committed policy remains `design_only`, `enabled:false`, `deployment_authorized:false`, and `live_publication_authorized:false`.

No installer or activation script is included. No Edge1 staging root, unit, timer, Apache include, route, listener, public artifact, or `/var/www` file has been created or changed.

Exact-head CI and final PR review are pending.

## Remaining separately authorized programs

- complete CI and merge review for the repository-only staging runtime;
- fresh authenticated Edge1 boundary inventory and separately authorized staging installation;
- authenticated detailed-operations browser/session boundary;
- separately authorized public cutover and detailed-artifact removal;
- separately authorized protected-retention installation and live acceptance.

## Safety boundary

No DNS, Unbound, RPZ, nftables rules, firewall, Fail2ban enforcement, routing, proxying, IDS rules, reputation lists, authentication, certificates, listeners, public routes, production traffic, timer scheduling, `/var/www` publication, release pruning, or data deletion changed.
