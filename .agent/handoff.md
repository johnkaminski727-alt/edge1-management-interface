# Edge1 Security Completion Programs Handoff

Date: 2026-07-30  
Repository: `johnkaminski727-alt/edge1-management-interface`  
Authoritative branch: `main`  
Baseline record revision: `83fdb08670f3b65dcdee705e440f1441efd5531e`  
Accepted live runtime revision: `a06f035e7fcf933a03ec752c66ce0261c5a65ba7`

## Accepted live baseline

Network Defense remains accepted with:

- freshness threshold `600` seconds;
- overall state `limited`;
- verified enforcement count `1` before and after activation;
- DNS policy `not_staged`;
- DNS enforcement false;
- traffic controls unchanged;
- timer state unchanged.

Protected baseline evidence:

```text
/var/lib/wwcx-deployment-evidence/edge1-project-completion-preflight/20260730T193415Z
/var/lib/wwcx-deployment-evidence/network-defense-freshness/20260730T195031Z
```

## Authorized repository implementation

The four security-completion programs have been implemented as a focused repository bundle:

1. **Protected Suricata retention** — consumes only the sanitized collector contract, stores root-only SQLite history, enforces time/count/size limits, deduplicates deterministically, verifies integrity, and preserves data on rollback.
2. **Minimized public summary** — packages the accepted seven-field allowlist exporter into a hardened oneshot/timer and isolated publication tree.
3. **Authenticated detailed operations** — stages `/edge1-ops/` behind Apache form/session authentication using an existing approved password file, encrypted secure session cookies, fail-closed anonymous access, audit events, and no-store/security headers.
4. **Public-boundary cutover** — proves authenticated access first, inventories/hashes/archives the detailed tree, switches `/edge1-status/` to minimized output, withdraws anonymous detailed routes, verifies authenticated equivalence, and restores the staged configuration on failure.

Repository validation currently passes 13 focused tests. The implementation creates no new listener and contains no credential material.

## Live execution fact

No new host deployment has been performed from the current runtime. There is no authenticated Edge1 shell or approved host connector available here, and root-protected authentication/acceptance files are intentionally inaccessible.

Therefore none of the following are claimed live yet:

- `wwcx-suricata-protected-retention.service` or `.timer`;
- `wwcx-edge1-minimized-public-summary.service` or `.timer`;
- `/var/lib/bigbird-security/suricata-history/`;
- `/var/lib/bigbird-public-status/www/`;
- `/edge1-login/` or `/edge1-ops/`;
- minimized `/edge1-status/` routing;
- new protected completion evidence directories.

## Exact host continuation

After exact-head CI passes and the pull request is merged, use the runbook:

```text
docs/security/edge1-security-completion-programs-runbook-20260730.md
```

The orchestrator is:

```text
deploy/activate-edge1-security-completion-programs.sh
```

It requires only paths to root-protected host files through:

```text
EDGE1_AUTH_USER_FILE
EDGE1_AUTH_ACCEPTANCE_FILE
```

Do not disclose their contents in chat. The cutover script cannot withdraw anonymous detail unless a browser-equivalent authenticated request succeeds first.

## Safety boundary

The bundle must not change DNS enforcement, Unbound, RPZ, nftables, firewall rules, routing, IDS rules, reputation lists, certificates, listeners, or production traffic. It archives before withdrawal, preserves operational data, and rolls back immediately on failed acceptance.
