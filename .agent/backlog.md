# Backlog

Last reconciled: 2026-08-20

This is the authoritative current Edge1 backlog. Completed historical commissioning checklists remain in dated acceptance/archive records and should not be reintroduced as active work without new contrary evidence.

## P1 — Security-boundary live inventory closeout

The read-only inventory has run successfully on Edge1.

- [x] Run `tools/security/edge1-security-boundary-live-inventory.sh` through an approved authenticated Edge1 path.
- [x] Record aggregate result: 164 records, 160 mapped, zero missing-known, four preserved unknowns, one filesystem anomaly.
- [x] Confirm Apache config testing passed and the inventory reported no configuration/source-tree/traffic-control mutation and no credentials collected.
- [x] Merge the fail-closed residual-artifact classifier and its regression tests.
- [ ] Record the exact timestamped protected evidence directory in durable closeout state.
- [ ] Run/retain classification of the four preserved unknowns and one filesystem anomaly using metadata/hash/path evidence only; do not read or move secret/private object contents merely for classification.
- [ ] Determine an actually available approved identity provider/Apache adapter from evidence before restricted-release work.
- [ ] Build a restricted release without modifying the authoritative source tree.
- [ ] Stage and accept authenticated `/edge1-ops/` before any anonymous detailed-route withdrawal.
- [ ] Stage/accept minimized public summary and protected Suricata retention before cutover.
- [ ] Archive/withdraw the detailed public tree only after authenticated equivalence and rollback acceptance.

DNS, firewall, certificates, authentication policy, listeners, and production traffic remain separately approval-gated.

## P1 — Control Surfaces evidence reconciliation

Current bounded diagnostics are healthy enough for operations. Asterisk native diagnostics now succeed through the accepted Asterisk-owned fixed snapshot path rather than relying on privilege-limited direct CLI access.

- [x] Re-test bounded summary/listeners/Asterisk/Kamailio/FreePBX diagnostics from the approved Edge1 operator path.
- [x] Keep the no-permission-widening decision: do not broaden Asterisk control-socket access merely to make diagnostic cards green.
- [x] Correct Git executable mode on `scripts/control-surfaces-live-inventory.sh` and merge the dedicated workflow validation.
- [x] Deploy/accept the bounded Asterisk snapshot producer/consumer mechanism.
- [x] Verify live `edge1.asterisk_status` reports `native_cli_status=ok` through `asterisk-owned-fixed-snapshot`.
- [ ] Retain a final executable Control Surfaces inventory manifest/summary if a later evidence record has not already captured it.
- [ ] Retain the corrected Asterisk warning-follow-up audit summary if not already captured in a later evidence record.
- [ ] Re-verify public/private route isolation after any future Control Surfaces behavior change.
- [ ] Keep any temporary/private FreePBX session broker blocked until authentication, expiry, revocation, CSRF, audit, redirects/cookies/WebSockets/CSP/X-Frame-Options, listener equivalence, and rollback are proven.

## P1 — Listener attribution / exposure provenance

Fresh bounded listener classification reports:

```text
internal-service=37
private-control=4
unknown-needs-attribution=22
```

These counts are attribution/provenance work, not automatic exposure defects.

- [ ] Attribute the remaining `unknown-needs-attribution` listeners through read-only service/configuration/process evidence.
- [ ] Reconcile accepted historical wildcard-service mappings before declaring any listener newly unexplained.
- [ ] Do not narrow, disable, firewall, rebind, or restart a listener solely because its classifier label is unknown.
- [ ] Require a separate reviewed change with consumer/rollback evidence for any eventual exposure reduction.

## P2 — DTMF provider response

Externally blocked pending provider response. Last retained mailbox state from 2026-08-19 showed no substantive technical reply after the 2026-08-14 notice that there was still no update.

- [ ] Receive a direct provider technical response.
- [ ] Retain the original response only in the restricted mailbox and create a sanitized response worksheet.
- [ ] Classify all nine answers by exact service scope and evidence strength.
- [ ] Leave ambiguous, indirect, best-effort, configuration-only, and test-required claims out of the carrier matrix.
- [ ] Run response/privacy/provider-evidence/cross-record/repository validators before any matrix update.
- [ ] Require separate explicit authorization before any controlled call or DTMF transmission.

Current gate remains:

```text
response_state=pending
provider_reply_received=false
matrix_update_allowed=false
live_test_authorized=false
```

## Deferred / optional

- [ ] Business159 staged-filesystem smoke acceptance may be run later as a new bounded acceptance activity if filesystem mutation capability needs independent proof. It was explicitly deferred at the 2026-08-20 archive closeout and must not be represented as previously passed. Keep deployment apply and raw shell separately gated.
- [ ] Consider promoting accepted Edge1 front-door HTTP 302 responses to 308 only after sufficient operational experience. This is not required for completion and is not automatically authorized.
- [ ] Review a shared tunnel-client upgrade only as a separately tested maintenance change; do not upgrade merely to change the historical old-doctor OAuth-metadata result while Big Bird depends on the current binary.

## Completed / do not reopen without new evidence

- [x] Business159 Secure MCP Tunnel **OPERATIONALLY COMPLETE / PERSISTENT / ARCHIVE READY** on 2026-08-20: dedicated service active/enabled, controlled restart passed, loopback `healthz=live`, `readyz=ready`, repository verifier passed, `NODE_OPTIONS=--jitless` retained with `MemoryDenyWriteExecute=yes`, and final marker `BUSINESS159_PERSISTENT_TUNNEL=PASS`.
- [x] Business159 workspace packaging accepted for archive: custom app enabled, 26 actions discovered, repo-scoped plugin installed by default, required app recognized, and the obsolete standalone skill removed to avoid shadowing. Final connector invocation was accepted for closeout by explicit operator direction rather than separately captured in archive evidence.
- [x] Business159 deployment apply and raw shell were not granted by this closeout; staged-filesystem smoke remains deferred and is not claimed as passed.
- [x] Edge1 public front door **LIVE / ACCEPTED / REVERIFIED** on 2026-08-19; canonical destination `https://ww.cx/time/`.
- [x] Edge1 front-door rollback/evidence preserved at `/var/backups/wwcx-edge1-front-door-approved-20260819T052836Z`.
- [x] Global `/etc/systemd/system` trust boundary restored to `root:root 0755` on 2026-08-20 with protected evidence.
- [x] Edge1 Secure MCP Tunnel compatibility gate accepted and tunnel activated.
- [x] Edge1 Secure MCP Tunnel persistent/active.
- [x] Edge1 Operator MCP commissioned at immutable runtime `d326d4546abefa695a293266342a5c1075f010e2`.
- [x] Operations API immutable runtime accepted at the same revision with mutations disabled.
- [x] Exact 16-tool public read-only MCP contract enforced at discovery and dispatch.
- [x] Bounded Asterisk-owned fixed snapshot mechanism deployed and accepted.
- [x] ChatGPT workspace publication **WORKSPACE PUBLISHED / ACCEPTED** with fresh-chat invocation evidence.
- [x] Persistent Operator turn-state root deployed without weakening `ProtectSystem=strict`.
- [x] Communications Relay / private News Reader closeout sealed with protected archive evidence.
- [x] Network Defense/Security Correlation accepted at its recorded checkpoint.
- [x] Asterisk `22.10.1` update accepted with rollback evidence.
- [x] Offline CAP-CP/EBS laboratory installed and synthetic tests accepted without operational feed/delivery.

Authoritative closeout records:

- `docs/business159-operator/2026-08-20-persistent-tunnel-closeout.md`;
- `docs/edge1-operator/17-post-deployment-acceptance-20260820.md`;
- `docs/edge1-operator/18-workspace-publication-acceptance-20260820.md`;
- `docs/edge1-operator/13-completion-status.md`.

## Hard boundaries

- Never place credentials, client secrets, password hashes, tokens, cookies, private keys, tunnel IDs/API keys, or raw alert contents in Git/chat/evidence.
- Never modify DNS, Unbound/RPZ, nftables/firewall, certificates, authentication policy, public listeners, carrier routing, emergency behavior, or production traffic solely from this backlog.
- Future privileged modifications to `/etc/systemd/system` remain separately approval-gated; the accepted 2026-08-20 repair does not grant standing authority for additional metadata or unit changes.
- Never originate production calls/messages or transmit DTMF/alerts without the separate explicit authorization required by those workstreams.
- Never delete retained evidence or sealed archives without tested rollback and explicit destructive-action approval.
- Inspect first, preserve unrelated work, back up before mutation, validate syntax/health/listeners, and retain rollback evidence.
