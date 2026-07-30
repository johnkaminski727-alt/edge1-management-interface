# Edge1 Project Completion Bundle Register

Date: 2026-07-30  
Classification: internal operations; no credentials or raw alert data  
System: Edge1 / WW.CX Security Observability  
Repository state: focused operator-bundle branch; not executed on Edge1

## Trigger

The security-observability repository phases are complete, but the following host-dependent work remained:

- live activation and acceptance of the Network Defense 600-second network-source freshness threshold;
- read-only Apache, route, header, CORS, directory-listing, and public-filesystem inventory;
- host sizing and SQLite evidence before protected Suricata-retention runtime implementation;
- protected evidence capture.

No authenticated Edge1 shell was available in the authoring runtime.

## Registered assets

| Asset | Purpose | Mutation boundary |
| --- | --- | --- |
| `deploy/activate-network-defense-freshness.sh` | Backup, install one service unit, execute one-shot exporter, verify endpoints, and roll back on failure | Installs only `wwcx-network-defense.service`; writes existing Network Defense status through the service |
| `tools/security/edge1-project-completion-preflight.sh` | Protected read-only host, Apache, route, header, filesystem, retention-size, and SQLite evidence | Writes only protected evidence and staged minimized output |
| `tests/test_edge1_project_completion_bundle.py` | Shell syntax and static safety validation | None |
| `docs/security/edge1-project-completion-runbook-20260730.md` | Exact operator sequence and claim boundary | None |

## Freshness activation controls

The activation script requires:

- root execution through an authenticated operator path;
- repository branch `main`;
- clean working tree;
- freshness merge `711952afb053fa3bd50c390516fa7b58f3943985` as an ancestor;
- required wrapper, service unit, validation script, and test files;
- protected evidence directory mode `0700`;
- backup of the installed unit and current status snapshot;
- automatic rollback after any post-mutation error.

It verifies:

- targeted tests and Network Defense repository validation;
- exact installed-unit equivalence;
- service result and exit status;
- network stale threshold `600`;
- unchanged verified-enforcement count;
- DNS policy `not_staged`;
- DNS enforcement false and unverified;
- `traffic_controls_changed:false`;
- unchanged timer enabled/active state;
- local and real-domain JSON acceptance;
- SHA-256 evidence.

It does not enable, disable, start, stop, or reschedule the timer.

## Completion preflight controls

The preflight captures:

- host, principal, repository, systemd, and capacity state;
- Apache syntax, vhost, module, and selected redacted directives;
- metadata and SHA-256 inventory for public-root files;
- anonymous local and public route/status/header results;
- cache, CSP, referrer, nosniff, CORS, and HSTS evidence;
- SQLite version, page limits, and compile options;
- sanitized alert count and serialized-size distribution without alert contents;
- staged minimized summary under the protected evidence directory;
- SHA-256 evidence manifest.

It performs no service control, Git update, Apache reload, authentication change, `/var/www` write, public route change, or protected-control mutation.

## Static validation requirements

The bundle validator requires:

- `bash -n` success for both scripts;
- branch, clean-worktree, ancestor, backup, rollback, and evidence gates;
- exact freshness, DNS, enforcement-count, traffic-control, and timer-state assertions;
- no timer mutation;
- no Apache reload or site/module activation;
- no DNS, resolver, firewall, nftables, Fail2ban, routing, IDS, or reputation mutation commands;
- no destructive Git commands;
- no public landing-page overwrite;
- no credentials, environment dump, SSH key, or shadow-file collection.

## Execution status

| Item | State |
| --- | --- |
| Repository implementation | In progress on focused branch |
| Exact-head CI | Pending |
| PR scope/merge review | Pending |
| Edge1 authenticated preflight | Not executed; no authenticated path in this runtime |
| Edge1 freshness activation | Not executed; no authenticated path in this runtime |
| Public cutover | Not authorized or performed |
| Protected-retention runtime | Not implemented or deployed |

## Remaining authority boundaries

Exact separate authorization remains required before:

- publishing the minimized summary under `/var/www`;
- changing Apache aliases, headers, authentication, proxying, or routes;
- removing currently published detailed artifacts;
- activating an authenticated browser/session boundary;
- certificate, listener, DNS, firewall, or production-traffic changes;
- deleting retained status, report, incident, or evidence data.

## Safety statement

The repository bundle changes no live host. It contains no credentials or raw alert records. It does not authorize public disclosure, authentication changes, traffic-control changes, or production cutover.
