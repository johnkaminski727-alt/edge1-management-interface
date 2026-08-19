# Backlog

Last reconciled: 2026-08-19

This is the authoritative current Edge1 backlog. Completed historical checklists remain in dated acceptance/archive records and should not be reintroduced here as active work.

## P0 — Permanent private Edge1 Operator / ChatGPT attachment

Server-side Operator, non-secret Secure MCP Tunnel staging, and local tunnel credential provisioning are complete. The service itself remains deliberately disabled/inactive pending attended activation and ChatGPT-side acceptance.

- [ ] Confirm the applicable ChatGPT developer/custom-app capability in the authorized workspace/account.
- [x] Create/select the Secure MCP Tunnel through the authorized account boundary.
- [x] Provision tunnel ID and runtime API key locally on Edge1 without exposing values in Git/chat/evidence.
- [x] Verify tunnel credential file ownership/mode/readability without displaying values.
- [x] Run the staged raw tunnel launcher doctor and capture the exact result without activating the service.
- [ ] Run `deploy/edge1-tunnel/validate-edge1-secure-mcp-tunnel-doctor.sh` on Edge1 and require `EDGE1_TUNNEL_COMPAT_DOCTOR=PASS`.
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

Raw doctor passed every prerequisite except `oauth_metadata`, which returned HTTP 404 and exit code 2. Exact installed upstream source unconditionally fails non-2xx OAuth metadata for every HTTP MCP target, while later upstream source explicitly treats all-404 OAuth metadata discovery as optional for plain/non-OAuth MCP servers. Edge1 intentionally uses its existing loopback bearer boundary plus tunnel `extra_headers` / `discovery_extra_headers`; do not add synthetic OAuth endpoints merely to satisfy the old doctor, and do not replace the shared tunnel binary solely for this result while Big Bird uses it.

The compatibility validator is pinned to the exact reviewed tunnel-client version and SHA before invoking doctor; an unreviewed replacement fails closed even if its raw doctor would pass.

Compatibility record:

`docs/edge1-operator/15-tunnel-doctor-compatibility-20260819.md`

Human/account credential material remains a stop boundary. No public MCP proxy, WAN listener, firewall opening, or authentication weakening is an acceptable substitute.

## P1 — Security-boundary live inventory and reconciliation

The read-only inventory has now run successfully on Edge1.

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
- [x] Correct the audit script so systemd-sysv informational stderr cannot create a false enablement warning; static safety validation passes in PR #450 CI.
- [ ] Rerun the corrected read-only audit on Edge1 and retain the final warning/failure summary.

The offline CAP-CP/EBS laboratory remains isolated. Connecting a CAP source, accepting `Actual` alerts, delivery adapters, calls/pages, tones, or public compatibility claims requires separate written authority/conformance evidence.

## P1 — Control Surfaces diagnostic reconciliation

- [x] Re-test bounded summary/listeners/Asterisk/Kamailio/FreePBX diagnostics from the approved Edge1 operator path.
- [x] Reconcile the native diagnostic degradation: constrained native CLI access falls back to successful passive evidence while higher-level telephony health remains healthy.
- [x] Determine that no permission widening or hardening reduction is justified merely to make those native cards green.
- [x] Correct Git executable mode on `scripts/control-surfaces-live-inventory.sh`; the dedicated inventory workflow passes in PR #450 CI.
- [ ] Fast-forward the clean Edge1 checkout after PR #450 merges and rerun the executable read-only inventory.
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
- [x] Communications Relay / private News Reader closeout sealed with protected archive evidence.
- [x] Network Defense/Security Correlation accepted at its recorded checkpoint.
- [x] Asterisk `22.10.1` update accepted with rollback evidence.
- [x] Offline CAP-CP/EBS laboratory installed and synthetic tests accepted without operational feed/delivery.

## Hard boundaries

- Never place credentials, client secrets, password hashes, tokens, cookies, private keys, tunnel IDs/API keys, or raw alert contents in Git/chat/evidence.
- Never modify DNS, Unbound/RPZ, nftables/firewall, certificates, authentication policy, public listeners, carrier routing, emergency behavior, or production traffic solely from this backlog.
- Never originate production calls/messages or transmit DTMF/alerts without the separate explicit authorization required by those workstreams.
- Never delete retained evidence or sealed archives without tested rollback and explicit destructive-action approval.
- Inspect first, preserve unrelated work, back up before mutation, validate syntax/health/listeners, and retain rollback evidence.
