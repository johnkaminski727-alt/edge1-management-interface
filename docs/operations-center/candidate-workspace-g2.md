# Edge1 Configuration Workspace G2 — private saved candidates

**Status:** staging branch, separate from Spamhaus PR #607 and installed G1. This is an opt-in, single-user local preview. Never present it as a deployed authenticated production configuration manager.

## What now works

- A private, loopback-only HTTP service exposes the browser UI and token-authenticated API at `127.0.0.1:8767`, accessible from Windows only through an operator-created SSH port forward.
- The operator enters an installation-generated random 256-bit access token into the browser. The token is kept in the browser tab's memory, never localStorage, and stored at `/var/lib/edge1-candidate-workspace-g2/access-token` with owner `wwadmin`, mode 0600 inside a 0700 data directory. Do not share the token in a transcript.
- Proposed dashboard, inventory and alert **display preferences** are strictly schema-validated, saved in a local SQLite database and survive page refresh or service restart. Every proposal requires the current candidate revision. Another browser tab cannot silently overwrite a changed candidate; reload after a 409 Conflict.
- Discard returns the candidate to the fixed demonstration running snapshot. Local timestamped audit entries record changed setting paths and before/after revision hashes. This is mutable local diagnostic history, **not** tamper-proof, attributable production security evidence.
- The API can read the pre-existing read-only `/var/www/edge1-status/core-status.json` observation. It exports only age/freshness and aggregate service counts; missing or stale observations are explicitly not healthy. It does **not** claim this is the live running configuration.
- There is no `/api/apply` route, no shell command execution, no write to real network/DNS/firewall settings, and no unattended background service.

## Architecture and safety boundary

`tools/operations/edge1_candidate_workspace.py` is the pure G1 validator/diff engine; `edge1_candidate_store.py` adds transactional SQLite persistence and optimistic compare-and-swap; `edge1_candidate_api.py` exposes the local HTTP service; and `src/web/operations-center/candidate-workspace-g2.html` is the self-contained UI. Browser changes are sent through authenticated, strict same-origin JSON requests. The API rejects unexpected Host headers, incorrect tokens, foreign POST Origins, oversized payloads, unknown settings and unknown mutation endpoints.

This is single-user **local development authentication**, not a substitute for a production security gateway or a publicly accessible administrative API. SSH tunnel access and token secrecy are required; do not publish or reverse proxy this service. Configuration stays separate from existing Operations Center and any reviewed safe-change runner operations. The local SQLite database does not constitute a protected audit ledger. Install scripts do not enable timers, systemd services, Apache routes, network ports or production firewall changes.

## Installation (operator approval required)

After pinning the reviewed branch commit, extract the installer and listed files into a temporary directory. Run `bash deploy/candidate-workspace/install-g2.sh --check` with `EDGE1_G2_SOURCE_ROOT` set to that directory. Then invoke `sudo env EDGE1_G2_SOURCE_ROOT=... bash ... --apply` as `wwadmin`; install requires `SUDO_USER=wwadmin`. Finally `sudo bash ... --verify`. The package installs to `/opt/edge1-candidate-workspace-g2`; data and private access token reside at `/var/lib/edge1-candidate-workspace-g2`. On future updates only an existing recognized G2 package may be replaced; the token and candidate database are preserved.

Stop any earlier local preview servers only if they use the same port. For an interactive private session from Windows PowerShell (do not paste token into chat), use:

```powershell
ssh -L 8767:127.0.0.1:8767 edge1 "python3 /opt/edge1-candidate-workspace-g2/edge1_candidate_api.py --ui /opt/edge1-candidate-workspace-g2/index.html --database /var/lib/edge1-candidate-workspace-g2/candidate.sqlite --token-file /var/lib/edge1-candidate-workspace-g2/access-token"
```

In a separate authenticated Edge1 shell, retrieve the token privately with `cat /var/lib/edge1-candidate-workspace-g2/access-token` and enter it into the browser UI at `http://127.0.0.1:8767/`. Avoid pasting terminal output that contains the secret. The Python service binds only 127.0.0.1 and runs only until Ctrl+C stops it. No login session or listener is installed persistently.

## Operator installation evidence — September 27, 2026

The operator fetched pinned and CI-validated revision `3ee4a7e9fb72c4449f0a2f9ab4e0c0a2d5f4c59f` on Edge1 and used a temporary `git archive` extraction rather than switching the active production repository branch. The G2 `--check` and `--apply` preflights each passed all 18 regression tests: eight G1 validator tests, six persistent candidate-store tests and four loopback API tests. The installer confirmed the API's loopback-only design and absence of an Apply endpoint, then installed files to `/opt/edge1-candidate-workspace-g2` and private data to `/var/lib/edge1-candidate-workspace-g2` without starting a service. `--verify` passed package SHA-256 checks and access-token ownership/mode checks. The operator retained the interactive SSH shell.

**Verified:** G2 local installation and test suite. **Not yet observed:** an actual Windows SSH tunnel, browser token authentication, browser candidate save/reload/discard, browser audit presentation or live observation rendering. No real Edge1 configuration changes or persistent background service were enabled. Do not publish the access token in incident evidence or chat logs.

## Tests and deferred G3 work

CI compiles and tests the G1 model, G2 persistence and G2 loopback HTTP API using temporary directories and an ephemeral port. Negative tests cover unauthorized requests, forbidden Origins, conflicting edits, invalid fields, persistence, restart, discard and stale/absent core observation. CI checks the installer in **check-only mode** and browser JS syntax. These checks do not verify deployment on the actual Edge1 host; the operator's pinned installation and verification output are separate gates.

A future G3 authenticated API must introduce identity-specific RBAC, CSRF/session protection, stronger audit integrity, separately validated read-only *real* running configuration sources, drift detection, and an approval-bound apply-job system using the reviewed allowlisted safe-change runner. Do not enable firewall/DNS/routing changes from this G2 prototype.
