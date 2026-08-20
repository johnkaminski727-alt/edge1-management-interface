# Backlog

Last reconciled: 2026-08-20

This is the authoritative current Edge1 backlog. Completed historical commissioning checklists remain in dated acceptance/archive records and should not be reintroduced as active work without new contrary evidence.

## P1 — CHR-15 BigBird connector lifecycle live acceptance

Source repair is merged in PR #478 (`28aa5c6c1ea24909f8a4765d4cc38c58fd46265a`), but current live acceptance is incomplete.

Fresh 2026-08-20 evidence:

```text
shared engineering checkout = 234d00194cf7ef4abb6bdd466c7d9a6f1996fd99
BigBird AI                  = 0.3.5-alpha.1 / healthy / enabled / read-only
Operations API              = healthy / 27 actions / mutations_enabled=false
bigbird-edge1-connector.service             = failed
bigbird-edge1-connector-maintenance.service = failed
```

- [x] Confirm merged source repair and its fail-closed 27-action classification.
- [x] Confirm current shared checkout predates PR #478 and both lifecycle units remain failed.
- [ ] Through an authenticated live-write path, identify exact worktree/unit/config state consumed by both units at mutation time.
- [ ] Back up source/config/unit state and preserve exact rollback reference.
- [ ] Deploy only the reviewed PR #478 prerequisites; do not drag unrelated `main` changes into the transaction.
- [ ] Run bounded refresh/start/restart acceptance and verify persistence, fail-closed unexpected-action handling, unchanged six enabled capabilities, BigBird/API read-only health, sibling tunnel health and listener invariants.

**BLOCKED:** current ChatGPT Edge1 Operator is read-only and does not expose the required backup/deploy/restart transaction. Keep CHR-15 open until genuine live acceptance exists.

## P1 — Security-boundary live inventory closeout

The read-only inventory has run successfully on Edge1.

- [x] Run `tools/security/edge1-security-boundary-live-inventory.sh` through an approved authenticated Edge1 path.
- [x] Record aggregate result: 164 records, 160 mapped, zero missing-known, four preserved unknowns, one filesystem anomaly.
- [x] Confirm Apache config testing passed and no configuration/source-tree/traffic-control mutation or credentials collection occurred.
- [x] Merge the fail-closed residual-artifact classifier and regression tests.
- [x] Record the exact protected evidence directory:
  `/var/lib/wwcx-deployment-evidence/edge1-security-boundary-live-inventory/20260819T060856Z`.
- [x] Retain result/manifest hashes in `docs/control-surfaces/project-big-bird-evidence-reconciliation-20260820.md`.
- [ ] Classify the four preserved unknowns and one filesystem anomaly using metadata/hash/path evidence only.

**BLOCKED:** the mounted bounded Operator does not expose the protected `reconciliation.json` / `public-filesystem-anomalies.json` metadata needed for the remaining five classifications. Do not read secret/private contents or delete preserved unknowns merely to force closure.

Restricted `/edge1-ops/` staging/cutover work remains a separate security-boundary stream; do not conflate it with residual evidence classification.

## P1 — Control Surfaces evidence reconciliation

Current bounded diagnostics are operational. Asterisk native diagnostics succeed through the accepted Asterisk-owned fixed snapshot path.

- [x] Re-test bounded summary/listeners/Asterisk/Kamailio/FreePBX diagnostics.
- [x] Preserve no-permission-widening decision for Asterisk control socket.
- [x] Correct Git executable mode on `scripts/control-surfaces-live-inventory.sh` and merge workflow validation.
- [x] Deploy/accept bounded Asterisk snapshot producer/consumer mechanism.
- [x] Verify live `edge1.asterisk_status` through `asterisk-owned-fixed-snapshot`.
- [x] Retain corrected Asterisk warning-follow-up audit evidence at `/var/lib/wwcx-deployment-evidence/asterisk-warning-followup/20260819T060845Z` with `asterisk_warning_audit_rc=0`.
- [ ] Retain a successful full executable `scripts/control-surfaces-live-inventory.sh` manifest/summary.

The 2026-08-19 full-script capture is explicitly **not** a success: `control_surfaces_inventory_rc=126`. No later durable full-script `rc=0` manifest was found. Current bounded Operator diagnostics are fresh equivalent operational evidence, but they do not retroactively turn that historical run into PASS.

## P1 — Listener attribution / exposure provenance

Fresh raw classifier remains:

```text
internal-service=37
private-control=4
unknown-needs-attribution=22
```

Evidence reconciliation in `docs/control-surfaces/project-big-bird-evidence-reconciliation-20260820.md` attributes 18 of those 22 conservative raw-unknown rows without changing exposure:

- private DNS on `10.77.0.1:53`;
- Chrony NTP on UDP 123;
- WireGuard on UDP 51820;
- Tailscale transport on UDP 41641;
- Kamailio SIP on private/public TCP/UDP 5060;
- NTS-KE on TCP 4460;
- FreePBX UCP Node/PM2 on TCP 8001/8003;
- Apache public front door on TCP 80/443.

Only four current rows remain genuinely unresolved by available bounded evidence:

```text
UDP  0.0.0.0:57784
UDP  [::]:51550
TCP  100.115.195.54:40463
TCP  fd7a:115c:a1e0::5d39:c337:42639
```

- [x] Reconcile accepted historical wildcard-service mappings before declaring listeners newly unexplained.
- [x] Attribute 18/22 conservative raw unknown rows through current/historical read-only evidence.
- [ ] Attribute the remaining four dynamic/Tailscale-local rows when exact process/consumer evidence becomes available.
- [ ] Do not narrow, disable, firewall, rebind, or restart a listener solely because its classifier label is unknown.
- [ ] Require a separate reviewed change with consumer/rollback evidence for any eventual exposure reduction.

The raw classifier may continue to report 22 until its static logic is deliberately changed. Do not modify classification code merely to improve a metric.

## P1 — CHR-18 shared-host Big Bird current verification

Latest retained accepted Business159 website deployment checkpoint:

```text
source=01ee93cf0337006c5d44031a5f9eb1a83e1d0100
release=/home/wwcxjywl/releases/ww-cx-website/20260819T201010Z
backup=/home/wwcxjywl/shared/ww-cx-website/backups/public-html-20260819T201010Z.tar.gz
```

The Business159 Secure MCP Tunnel itself is **OPERATIONALLY COMPLETE / PERSISTENT / ARCHIVE READY** and must not be reopened absent contrary evidence.

- [ ] Reinspect the current Business159 application checkout, document/public root, release/deployment state, working tree/source revision and relevant PHP/HTTP behavior through an authenticated host path.
- [ ] Verify whether historical `/home/wwcxjywl/staging.ww.cx` and `/home/wwcxjywl/project-big-bird-private/` remain active, moved or superseded.
- [ ] Leave production unchanged if already correct; do not deploy merely to make documentation equal repository `main`.

**BLOCKED:** no current authenticated Business159 filesystem/shell execution connector is mounted. Keep CHR-18 open.

## P1 — Project Big Bird Library/archive reconciliation

- [x] Canonical Project Big Bird primary private-library sync set identified as ten unique hashes with no exact duplicates inside that primary set.
- [x] Current BigBird target Library observed healthy at 1 collection / 63 documents / 501 chunks / 0 rejected.
- [x] Release/version map and deployment/backup/rollback matrix created and merged in `ww-cx-website` PR #86.
- [ ] Update/retain canonical Library copies to the current reconciled state as provider capabilities permit.
- [ ] Import/re-index the newer canonical source set only through a reviewed bounded BigBird write/import path.
- [ ] Continue root/loose pasted/intermediate classification under the existing cleanup register; do not create duplicate source-of-truth packages or delete unique evidence.

**BLOCKED for target import:** current Edge1 Operator is read-only.

## P2 — DTMF provider response

Gmail was rechecked 2026-08-20. The newest VoIP.ms technical-thread response remains the 2026-08-14 notice that there were no updates; no substantive later technical reply was found.

```text
response_state=pending
provider_reply_received=false
matrix_update_allowed=false
live_test_authorized=false
```

- [ ] Receive a direct substantive provider technical response.
- [ ] Retain original only in restricted mailbox and create a sanitized worksheet.
- [ ] Classify answers by exact service scope/evidence strength.
- [ ] Leave ambiguous/test-required claims out of carrier matrix.
- [ ] Require separate explicit authorization before any controlled call or DTMF transmission.

## Completed / do not reopen without new evidence

- [x] Project Big Bird CHR-16 version-namespace/release map reconciled; canonical matrix merged in `ww-cx-website` PR #86.
- [x] Project Big Bird CHR-17 deployment/backup/rollback matrix completed in the same canonical record; no competing source of truth created.
- [x] Business159 Secure MCP Tunnel persistent closeout accepted 2026-08-20.
- [x] Edge1 public front door LIVE / ACCEPTED / REVERIFIED 2026-08-19.
- [x] Global `/etc/systemd/system` trust boundary restored to `root:root 0755` with protected evidence.
- [x] Edge1 Secure MCP Tunnel active/persistent and Edge1 Operator MCP commissioned at immutable runtime `d326d4546abefa695a293266342a5c1075f010e2`.
- [x] Operations API accepted at same immutable revision with mutations disabled.
- [x] Exact 16-tool public read-only MCP contract enforced.
- [x] Bounded Asterisk-owned fixed snapshot mechanism deployed and accepted.
- [x] Communications Relay/private News Reader, network defense, Asterisk update, and offline CAP-CP/EBS laboratory remain at their accepted historical checkpoints.

## Deferred / optional

- [ ] Business159 staged-filesystem smoke may be run later as a new bounded acceptance activity if filesystem mutation proof is needed. It was explicitly deferred and is not claimed passed.
- [ ] Consider front-door 302→308 only as a separate future change.
- [ ] Shared tunnel-client upgrade remains separate maintenance; do not upgrade merely to change historical doctor output.

## Hard boundaries

Never place credentials, secrets, tokens, cookies, private keys, tunnel secrets, protected customer data, or unnecessary sensitive personal data in Git/chat/evidence. Never modify DNS, firewall, certificates, authentication policy, public listeners, carrier routing, emergency behavior, production traffic, calls/messages/DTMF/alerts, or retained evidence solely from this backlog. Never force-push, rewrite history, or delete sealed evidence without tested rollback and explicit destructive approval. Inspect first, preserve unrelated work, back up before live mutation, validate, verify, record, and preserve rollback.
