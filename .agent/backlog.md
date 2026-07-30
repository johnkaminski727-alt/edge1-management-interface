# Backlog

## Completed live baseline

- [x] Security Correlation and Network Defense deployed and accepted.
- [x] Suricata drill-down, caching, normalization, and enrichment deployed.
- [x] Network Defense freshness threshold activated and accepted at `600` seconds.
- [x] Verified enforcement count remained `1` before and after activation.
- [x] DNS remains `not_staged`; DNS enforcement remains false.
- [x] Network Defense timer state and traffic controls remained unchanged.

## Completed repository implementation

- [x] Record exact authorization and immutable guardrails for all four security-completion programs.
- [x] Implement protected sanitized Suricata retention runtime.
- [x] Enforce 30-day, 100,000-event, and 256-MiB retention ceilings.
- [x] Add deterministic deduplication, strict allowlisting, atomic writes, integrity checks, and data-preserving rollback.
- [x] Add separate hardened retention service and timer.
- [x] Package the minimized public-status exporter as a hardened service and timer.
- [x] Add an isolated minimized publication tree.
- [x] Add an Apache form/session boundary for `/edge1-ops/` using an existing approved password file.
- [x] Require encrypted secure HttpOnly SameSite session cookies, no directory listing, no wildcard CORS, and no-store headers.
- [x] Add browser-equivalent authenticated acceptance and fail-closed anonymous checks.
- [x] Add archive-before-withdrawal public cutover and exact anonymous 404 checks.
- [x] Preserve the detailed tree and protected archive; do not destructively delete records.
- [x] Add read-only preflight, rollback, protected evidence, and SHA-256 manifests.
- [x] Pass 13 focused local repository tests plus Python compilation, JSON validation, and shell syntax validation.
- [x] Add runbook, register, and `.agent` continuity updates.

## Remaining exact-head repository gates

- [ ] Open the focused pull request against `main`.
- [ ] Pass exact-head `Validate repository`.
- [ ] Pass exact-head `Edge1 Operator Validation`.
- [ ] Confirm changed-file scope, zero-behind state, mergeability, and no unresolved review threads.
- [ ] Merge only the exact validated head.

## Remaining authenticated host sequence

- [ ] Establish an approved authenticated Edge1 execution path without sharing credentials in chat.
- [ ] Fast-forward a clean `/opt/edge1-management-interface` checkout to the exact merged `main` revision.
- [ ] Provide the path to an existing approved root-owned Apache password file through `EDGE1_AUTH_USER_FILE`.
- [ ] Provide a temporary root-owned mode-`0600` acceptance JSON file through `EDGE1_AUTH_ACCEPTANCE_FILE`.
- [ ] Run `tools/security/edge1-security-completion-preflight.sh` and review its protected manifest.
- [ ] Deploy and accept protected Suricata retention.
- [ ] Stage and accept authenticated `/edge1-ops/` while leaving anonymous detail unchanged.
- [ ] Archive the detailed public tree and perform the minimized `/edge1-status/` cutover.
- [ ] Confirm anonymous detailed routes return `404`, authenticated detailed routes return `200`, headers are correct, and listeners/control planes remain unchanged.
- [ ] Record exact evidence paths and live acceptance results in the register and `.agent` files.

## Hard stop boundaries

- Never request or copy passwords, password hashes, tokens, cookies, private keys, or session keys into chat or Git.
- Stop and roll back if authentication, route isolation, public minimization, service health, data integrity, or listener equivalence fails.
- Do not delete the retention database, detailed tree, archives, incident records, reports, or deployment evidence.
- Do not alter DNS enforcement, Unbound, RPZ, nftables, firewall rules, routing, IDS rules, reputation lists, certificates, or production traffic.
