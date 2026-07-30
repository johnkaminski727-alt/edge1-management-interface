# Current State

Last verified: 2026-07-30  
Repository: `johnkaminski727-alt/edge1-management-interface`  
Authoritative branch: `main`  
Authoritative base: `4d2e717f8b0475fed574a4a6114c1a318d7e9655`  
Current branch: `ops/edge1-project-completion-bundle-20260730`

## Verified live baseline

- Security Correlation and Network Defense are live and accepted.
- Suricata drill-down, caching, normalization, and enrichment are live.
- Spamhaus, Fail2ban, and nftables report accepted truthful states.
- DNS remains unstaged and disabled; traffic controls remain unchanged.

## Repository-complete phases

- Network Defense freshness implementation and repository closeout through PR #127; live activation remains unclaimed.
- Protected Suricata retention design through PR #129; policy disabled and no runtime deployed.
- Public access-boundary design through PR #131.
- Minimized public summary implementation and closeout through PR #133 at `4d2e717f8b0475fed574a4a6114c1a318d7e9655`.

## Current repository phase — operator completion bundle

The branch adds:

- `deploy/activate-network-defense-freshness.sh`;
- `tools/security/edge1-project-completion-preflight.sh`;
- `tests/test_edge1_project_completion_bundle.py`;
- `docs/security/edge1-project-completion-runbook-20260730.md`;
- `registers/edge1-project-completion-bundle-register-20260730.md`.

### Bounded freshness activation

The activation script:

- requires authenticated root execution, clean `main`, and the merged freshness commit;
- backs up the installed service unit and current Network Defense snapshot;
- installs only `wwcx-network-defense.service`;
- does not modify the timer;
- executes one one-shot export;
- verifies threshold `600`, unchanged enforcement count, DNS `not_staged`, DNS enforcement false, and `traffic_controls_changed:false`;
- verifies local and real-domain JSON;
- automatically restores the saved unit and snapshot on failure;
- records protected evidence and SHA-256 hashes.

### Protected completion preflight

The read-only preflight captures:

- host, principal, Git, systemd, and capacity state;
- Apache syntax, vhost, module, and redacted directive inventory;
- public-root file metadata and hashes;
- local/public route and security-header matrix;
- SQLite capabilities and sanitized Suricata size/rate evidence;
- a staged minimized public summary under the protected evidence directory.

It performs no service control, Apache reload, authentication change, route change, `/var/www` write, or traffic-control mutation.

## Execution status

- No authenticated Edge1 connector, SSH configuration, or key material is available in this runtime.
- The operator bundle has not been executed on Edge1.
- Repository exact-head CI, PR scope review, and merge remain pending.
- No public cutover, authentication staging, detailed-artifact removal, or protected-retention runtime is authorized or claimed.

## Safety boundary

No DNS, Unbound, RPZ, nftables, firewall, Fail2ban, routing, proxying, IDS, reputation list, authentication, certificate, listener, public route, `/var/www` publication, deletion, or production traffic is changed by this repository phase.
