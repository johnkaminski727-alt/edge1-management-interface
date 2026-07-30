# Edge1 Security Observability Project Completion Runbook

Date: 2026-07-30  
Repository: `johnkaminski727-alt/edge1-management-interface`  
Host repository: `/opt/edge1-management-interface`  
Status: operator bundle prepared; authenticated host execution still required

## Objective

Finish the remaining bounded Edge1 work without changing DNS, resolver policy, firewall rules, nftables, Fail2ban, IDS rules, reputation controls, proxy routing, authentication, certificates, listeners, public routes, or production traffic.

The completion sequence has two independently auditable operations:

1. protected read-only host inventory and staging;
2. narrow Network Defense freshness activation.

No public-boundary cutover is included.

## Operator prerequisites

The operator must have an authenticated shell on Edge1 with documented privilege escalation. Do not pass credentials, private keys, tokens, cookies, or recovery material through chat or repository files.

Before either command:

```bash
cd /opt/edge1-management-interface
git status --short --branch
git rev-parse HEAD
```

Requirements:

- branch is `main`;
- worktree is clean;
- authoritative `main` contains the merged completion bundle;
- no unrelated work is reset, cleaned, stashed, overwritten, or deleted.

## Step 1 — read-only completion preflight

Run:

```bash
sudo bash tools/security/edge1-project-completion-preflight.sh
```

The script writes protected evidence beneath:

```text
/var/lib/wwcx-deployment-evidence/edge1-project-completion-preflight/<UTC timestamp>/
```

It records:

- host, principal, kernel, capacity, repository, and systemd state;
- Apache syntax, vhost, module, and selected redacted directive inventory;
- public-root file metadata and SHA-256 inventory without copying file contents;
- anonymous local and real-domain route/status/header matrix;
- cache, CSP, referrer, nosniff, CORS, HSTS, and directory-route evidence;
- SQLite version, page behavior, compile options, and filesystem capacity;
- sanitized Suricata alert-size distribution and count without alert contents;
- a build-scoped minimized public summary and page under the evidence directory;
- an evidence SHA-256 manifest.

The script does not:

- reload Apache;
- alter authentication or headers;
- write to `/var/www`;
- change services, timers, listeners, DNS, firewall, or routing;
- publish or remove any public artifact.

## Step 2 — bounded freshness activation

Run only after Step 1 succeeds:

```bash
sudo bash deploy/activate-network-defense-freshness.sh
```

The activation changes only the installed `wwcx-network-defense.service` unit so it invokes the already-merged final freshness wrapper. The timer is not enabled, disabled, started, stopped, or rescheduled.

Evidence is written beneath:

```text
/var/lib/wwcx-deployment-evidence/network-defense-freshness/<UTC timestamp>/
```

Acceptance requires:

- repository `main` is clean and contains freshness merge `711952afb053fa3bd50c390516fa7b58f3943985`;
- targeted repository validation passes;
- installed unit exactly matches the repository unit;
- one-shot service result is `success` with exit status `0`;
- `sources.network.stale_after_seconds` is exactly `600`;
- `verified_enforcement_count` does not change from the captured baseline;
- DNS policy remains `not_staged`;
- DNS enforcement remains disabled and unverified;
- `traffic_controls_changed` remains false;
- timer enablement and active state are unchanged;
- local and real-domain JSON both report the accepted threshold and no traffic-control change;
- SHA-256 and protected terminal evidence are captured.

## Rollback

If activation fails after mutation begins, the script automatically restores:

- the prior installed service unit or its prior absence;
- the prior Network Defense JSON snapshot or its prior absence;
- systemd's loaded unit state through `daemon-reload`.

The script does not alter the timer, so timer enablement and scheduling do not require rollback.

Failure evidence is retained with `rolled_back=true` and the command exit status.

## Interpretation of preflight results

The preflight completes the evidence needed for two future decisions but does not authorize either decision.

### Protected Suricata retention

Review:

- `suricata-retention-sizing.json`;
- `sqlite-capability.json`;
- `filesystem-capacity.txt`.

The accepted repository design remains disabled. Runtime implementation still requires a separate branch and review using the measured host evidence.

### Public access boundary

Review:

- `apache-vhosts.txt`;
- `apache-directives.txt`;
- `public-filesystem-inventory.txt`;
- `route-matrix.tsv`;
- `route-header-summary.json`.

The minimized summary remains staged only under protected evidence. Publication, Apache/header changes, authentication staging, detailed-artifact removal, or public cutover require exact separate authorization and rollback evidence.

## Completion claim boundary

The repository portion is complete when the bundle passes exact-head CI and merges.

The freshness activation may be called live-complete only after the host evidence proves every acceptance item above.

The broader public-boundary project may not be called cut over until a separately authorized deployment establishes minimized anonymous output and fail-closed authenticated detailed operations.
