# Backlog

Last reconciled: 2026-08-20

This is the authoritative current Edge1 backlog. Completed historical checklists remain in dated acceptance/archive records and should not be reintroduced here as active work.

## P0 — Restore global systemd unit-directory trust boundary

The hardened Secure MCP preactivation validator exposed a separate production filesystem trust-boundary defect before tunnel activation. The defect is now repaired and verified.

Accepted live state:

```text
/etc/systemd/system owner=root:root mode=0755
/etc/systemd/system/edge1-secure-mcp-tunnel.service owner=root:root mode=0644
edge1-secure-mcp-tunnel.service sha256=a79a7ae19b2fb639c34a895c36b3ef3055a83b2342e037ddf60546cdda4d77dd
```

Protected production evidence:

```text
/var/lib/wwcx-deployment-evidence/systemd-unit-dir-boundary/20260820T011819Z
```

- [x] Identify the exact live traversal failure without changing permissions.
- [x] Verify the tunnel unit itself has the reviewed root ownership, mode, path, and SHA-256.
- [x] Identify the repository root cause in `deploy/install-time-authority-edge1.sh`.
- [x] Correct Time Authority preflight so production requires `/etc/systemd/system` to remain `root:root` mode `0755`.
- [x] Correct Time Authority installer so `bigbird-time` owns only its application data directory, never the global systemd unit directory.
- [x] Add regression CI validation for this trust boundary.
- [x] Prepare fail-closed dry-run-first remediation tool `deploy/repair-edge1-systemd-unit-dir-boundary.sh`.
- [x] Merge the systemd-boundary hardening after exact-head CI.
- [x] Obtain explicit production security-change approval before remediation `--apply`.
- [x] Run remediation dry-run and verify the exact known drift `bigbird-time:bigbird-time 0750 -> root:root 0755`.
- [x] Apply the approved metadata-only repair with protected evidence and rollback record.
- [x] Verify immediate `/etc/systemd/system` entries and relevant service active/enabled states remained unchanged.
- [x] Verify `edge1-operator` can traverse/read the world-readable Edge1 tunnel unit after the safe parent-directory restoration.

Finding/acceptance record:

`docs/security/edge1-systemd-unit-dir-boundary-20260819.md`

Do not weaken the MCP validator or grant `edge1-operator` membership in `bigbird-time` as a workaround. Do not restore the prior service-account-owned systemd directory state except as an explicitly reviewed emergency rollback.

## P0 — Permanent private Edge1 Operator / ChatGPT attachment

Server-side Operator, non-secret Secure MCP Tunnel staging, local tunnel credential provisioning, and the prerequisite systemd trust-boundary repair are complete. The tunnel service itself remains deliberately disabled/inactive pending hardened compatibility validation, attended activation, and ChatGPT-side acceptance.

- [ ] Confirm the applicable ChatGPT developer/custom-app capability in the authorized workspace/account.
- [x] Create/select the Secure MCP Tunnel through the authorized account boundary.
- [x] Provision tunnel ID and runtime API key locally on Edge1 without exposing values in Git/chat/evidence.
- [x] Verify tunnel credential file ownership/mode/readability without displaying values.
- [x] Run the staged raw tunnel launcher doctor and capture the exact result without activating the service.
- [x] Merge PR #450 and fast-forward the clean Edge1 checkout to its accepted merge state.
- [x] Merge PR #452 after exact-head CI; it closes the post-review fail-closed gaps in the preactivation validator and staging installer.
- [x] Fast-forward the clean Edge1 checkout through the reviewed systemd-boundary remediation head.
- [x] Run the hardened validator once; it failed closed before doctor because the then-unsafe global systemd directory was not traversable by `edge1-operator`.
- [x] Restore the global systemd unit-directory trust boundary under explicit production approval.
- [ ] Rerun `deploy/edge1-tunnel/validate-edge1-secure-mcp-tunnel-doctor.sh` read-only and require `EDGE1_TUNNEL_COMPAT_DOCTOR=PASS`.
- [ ] Start `edge1-secure-mcp-tunnel.service` attended, without persistence, only after the compatibility gate passes and the activation boundary is explicitly approved.
- [ ] Verify Big Bird tunnel remains healthy and unchanged.
- [ ] Verify Edge1 MCP remains bearer-protected and loopback-only on `127.0.0.1:8102`.
- [ ] Verify tunnel `/healthz` and `/readyz` from its dynamically selected loopback health URL.
- [ ] Scan tools from ChatGPT and require exactly the reviewed 16 named parameterless read-only tools.
- [ ] Prove ChatGPT-side `edge1.identity`, `edge1.health`, and approved diagnostics.
- [ ] Prove durable Edge1 audit evidence.
- [ ] Test attended stop plus documented account-side tunnel/key revocation path.
- [ ] Enable tunnel persistence only after attended acceptance passes.
- [ ] Record final permanent-Operator closeout.

### Raw doctor compatibility finding

The installed shared tunnel-client remains the accepted build:

```text
0.0.10+105e17a79a36e4e5c897fd698ed2b8dbf935b144
sha256=937347720ef32ef3ef2f68f4496b2dd7917ca5e575452ed87a4ce78d0262a100
```

Raw doctor passed every prerequisite except `oauth_metadata`, which returned HTTP 404 and exit code 2. Exact installed upstream source unconditionally fails non-2xx OAuth metadata for every HTTP target, while later upstream source explicitly treats all-404 OAuth metadata discovery as optional for plain/non-OAuth MCP servers. Edge1 intentionally uses its existing loopback bearer boundary plus tunnel `extra_headers` / `discovery_extra_headers`; do not add synthetic OAuth endpoints merely to satisfy the old doctor, and do not replace the shared tunnel binary solely for this result while Big Bird uses it.

PR #452 hardened the validator to pin the reviewed launcher/config/unit hashes and file ownership/modes, prove unauthenticated MCP 401 plus authenticated GET `/mcp` 405, and require the exact reviewed OAuth-metadata-only raw-doctor failure. The filesystem trust-boundary blocker that prevented this validator from reaching those checks has now been repaired; rerunning the validator is the next read-only gate.

Compatibility records:

- `docs/edge1-operator/14-secure-mcp-tunnel.md`
- `docs/edge1-operator/15-tunnel-doctor-compatibility-20260819.md`

Human/account credential material remains a stop boundary. No public MCP proxy, WAN listener, firewall opening, authentication weakening, or cross-service group-membership workaround is acceptable.

## P1 — Security-boundary live inventory and reconciliation

The read-only inventory has run successfully on Edge1.

- [x] Run `tools/security/edge1-security-boundary-live-inventory.sh` through the approved authenticated Edge1 path.
- [ ] Record the exact timestamped protected evidence directory in durable closeout state.
- [x] Record aggregate result: 164 records, 160 mapped, zero missing-known, four preserved unknowns, one filesystem anomaly.
- [x] Confirm Apache config testing passed and the inventory reported no configuration/source-tree/traffic-control mutation and no credentials collected.
- [ ] Classify the four preserved unknowns and one filesystem anomaly using metadata/hash/path evidence only; do not read or move secret/private object contents merely for classification.
- [ ] Determine an actually available approved identity provider/Apache adapter from evidence before restricted-release work.
- [ ] Build a restricted release without modifying the authoritative source tree.
- [ ] Stage and accept authenticated `/edge1-ops/` before any anonymous detailed-route withdrawal.
- [ ] Stage/accept minimized public summary and protected Suricata retention before cutover.
- [ ] Archive/withdraw the detailed public tree only after authenticated equivalence and rollback acceptance.

DNS, firewall, certificates, authentication policy, listeners, and production traffic remain separately approval-gated.

## P1 — Asterisk / alerting warning follow-up

The read-only service/configuration investigation is complete. No listener, firewall, certificate, SIP, or startup-policy mutation is indicated.

- [x] Run `tools/alerting/asterisk_warning_followup_audit.sh` on Edge1 and retain protected evidence.
- [x] Reconcile PJSIP transport visibility: a configured transport and Asterisk-owned loopback UDP `127.0.0.1:5061` are present.
- [x] Verify boot persistence: Asterisk is active and SysV `S01asterisk` startup links are present in runlevels 2-5; systemd-sysv reports enabled.
- [x] Verify TCP `8089` is loopback-only and completes a local TLS 1.3 handshake using the Edge1 certificate.
- [x] Disposition the live findings as expected/contained; zero failures require production mutation.
- [x] Correct the audit script so systemd-sysv informational stderr cannot create a false enablement warning; static safety validation passed in PR #450 CI.
- [ ] Rerun the corrected read-only audit on Edge1 and retain the final warning/failure summary.

The offline CAP-CP/EBS laboratory remains isolated. Connecting a CAP source, accepting `Actual` alerts, delivery adapters, calls/pages, tones, or public compatibility claims requires separate written authority/conformance evidence.

## P1 — Control Surfaces diagnostic reconciliation

- [x] Re-test bounded summary/listeners/Asterisk/Kamailio/FreePBX diagnostics from the approved Edge1 operator path.
- [x] Reconcile the native diagnostic degradation: constrained native CLI access falls back to successful passive evidence while higher-level telephony health remains healthy.
- [x] Determine that no permission widening or hardening reduction is justified merely to make those native cards green.
- [x] Correct Git executable mode on `scripts/control-surfaces-live-inventory.sh`; the dedicated inventory workflow passed in PR #450 CI.
- [x] Fast-forward the clean Edge1 checkout through that executable-mode fix.
- [ ] Rerun the executable read-only inventory and retain its manifest/summary.
- [ ] Re-verify public/private route isolation after any future Control Surfaces behavior change.
- [ ] Keep any temporary/private FreePBX session broker blocked until authentication, expiry, revocation, CSRF, audit, redirects/cookies/WebSockets/CSP/X-Frame-Options, listener equivalence, and rollback are proven.

## P2 — DTMF provider response

Externally blocked pending provider response. Mailbox was rechecked on 2026-08-19; the latest provider message remains the 2026-08-14 notice that there is no update yet.

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

- [ ] Consider promoting accepted Edge1 front-door HTTP 302 responses to 308 only after sufficient operational experience. This is not required for completion and is not automatically authorized.
- [ ] Review a shared tunnel-client upgrade only as a separately tested maintenance change; do not upgrade merely to change the old doctor result while Big Bird depends on the current binary.

## Completed / do not reopen without new evidence

- [x] Edge1 public front door LIVE / ACCEPTED on 2026-08-19; canonical destination `https://ww.cx/time/`.
- [x] Edge1 front-door rollback/evidence preserved at `/var/backups/wwcx-edge1-front-door-approved-20260819T052836Z`.
- [x] Edge1 server-side bounded MCP Operator verified live on loopback.
- [x] Non-secret Secure MCP Tunnel host staging accepted.
- [x] Secure MCP Tunnel local ID/runtime-key files provisioned with restricted metadata; values never recorded in Git/chat.
- [x] Global `/etc/systemd/system` trust boundary restored to `root:root 0755` on 2026-08-20 with evidence at `/var/lib/wwcx-deployment-evidence/systemd-unit-dir-boundary/20260820T011819Z`.
- [x] Communications Relay / private News Reader closeout sealed with protected archive evidence.
- [x] Network Defense/Security Correlation accepted at its recorded checkpoint.
- [x] Asterisk `22.10.1` update accepted with rollback evidence.
- [x] Offline CAP-CP/EBS laboratory installed and synthetic tests accepted without operational feed/delivery.

## Hard boundaries

- Never place credentials, client secrets, password hashes, tokens, cookies, private keys, tunnel IDs/API keys, or raw alert contents in Git/chat/evidence.
- Never modify DNS, Unbound/RPZ, nftables/firewall, certificates, authentication policy, public listeners, carrier routing, emergency behavior, or production traffic solely from this backlog.
- Future privileged modifications to `/etc/systemd/system` remain separately approval-gated; the accepted 2026-08-20 repair does not grant standing authority for additional metadata or unit changes.
- Never originate production calls/messages or transmit DTMF/alerts without the separate explicit authorization required by those workstreams.
- Never delete retained evidence or sealed archives without tested rollback and explicit destructive-action approval.
- Inspect first, preserve unrelated work, back up before mutation, validate syntax/health/listeners, and retain rollback evidence.
