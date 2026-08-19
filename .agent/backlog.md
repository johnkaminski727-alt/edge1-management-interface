# Backlog

Last reconciled: 2026-08-19

This is the authoritative current Edge1 backlog. Completed historical checklists remain in dated acceptance/archive records and should not be reintroduced here as active work.

## P0 — Permanent private Edge1 Operator / ChatGPT attachment

Server-side Operator and non-secret Secure MCP Tunnel staging are already complete. Remaining work is the account/workspace credential boundary and end-to-end acceptance.

- [ ] Enable the applicable ChatGPT developer/custom-app capability in the authorized workspace/account.
- [ ] Create/select the Secure MCP Tunnel for Edge1 through the authorized account boundary.
- [ ] Provision tunnel ID and runtime API key locally on Edge1 without exposing values in Git/chat/evidence.
- [ ] Verify tunnel credential file ownership/mode without displaying values.
- [ ] Run the staged Edge1 tunnel launcher `doctor` successfully.
- [ ] Start `edge1-secure-mcp-tunnel.service` attended, without persistence.
- [ ] Verify Big Bird tunnel remains healthy and unchanged.
- [ ] Verify Edge1 MCP remains bearer-protected and loopback-only on `127.0.0.1:8102`.
- [ ] Scan tools from ChatGPT and require exactly the reviewed 16 named parameterless read-only tools.
- [ ] Prove ChatGPT-side `edge1.identity` and `edge1.health`.
- [ ] Prove approved read-only diagnostics and durable audit evidence.
- [ ] Test service stop/disable plus documented account-side tunnel/key revocation path.
- [ ] Enable tunnel persistence only after attended acceptance passes.
- [ ] Record final permanent-Operator closeout.

Human/account credential material is an explicit stop boundary. No public MCP proxy, WAN listener, firewall opening, or authentication weakening is an acceptable substitute.

## P1 — Security-boundary live inventory and reconciliation

The inventory package is merged and read-only but still needs current authenticated host evidence.

- [ ] Run `tools/security/edge1-security-boundary-live-inventory.sh` through the approved authenticated Edge1 path.
- [ ] Record the exact protected evidence directory.
- [ ] Record aggregate reconciliation counts and fail-closed result without copying private objects into Git.
- [ ] Review every unknown, missing, prefix-contained, duplicate, stale, historical, and operator-maintained artifact.
- [ ] Confirm the inventory reports no configuration/source-tree/traffic-control mutation and no credentials collected.
- [ ] Determine an actually available approved identity provider/Apache adapter from evidence before restricted-release work.
- [ ] Build a restricted release without modifying the authoritative source tree.
- [ ] Stage and accept authenticated `/edge1-ops/` before any anonymous detailed-route withdrawal.
- [ ] Stage/accept minimized public summary and protected Suricata retention before cutover.
- [ ] Archive/withdraw the detailed public tree only after authenticated equivalence and rollback acceptance.

DNS, firewall, certificates, authentication policy, listeners, and production traffic remain separately approval-gated.

## P1 — Asterisk / alerting warning follow-up

Read-only audit first; no listener/startup/security mutation follows automatically from a warning.

- [ ] Run `tools/alerting/asterisk_warning_followup_audit.sh` on Edge1 and retain sanitized evidence.
- [ ] Reconcile `pjsip show transports` visibility against Asterisk-owned loopback UDP `127.0.0.1:5061`.
- [ ] Verify Asterisk boot persistence using SysV startup links and generated/systemd wrapper behavior before any enablement change.
- [ ] Verify TCP `8089` bind scope, TLS identity, authentication/firewall reachability, and operational need before any listener change.
- [ ] Reconcile any warning into a documented disposition: expected, configuration drift, security concern, or unresolved.

The offline CAP-CP/EBS laboratory remains isolated. Connecting a CAP source, accepting `Actual` alerts, delivery adapters, calls/pages, tones, or public compatibility claims requires separate written authority/conformance evidence.

## P1 — Control Surfaces diagnostic reconciliation

- [ ] Re-test the native Asterisk/Kamailio/FreePBX diagnostic actions from the bounded Operations API / Operator path.
- [ ] Determine why any native diagnostic card remains degraded while higher-level telephony health is healthy.
- [ ] Fix only the smallest evidence-backed diagnostic issue that does not widen permissions or weaken hardening.
- [ ] Re-verify public/private route isolation after any future Control Surfaces change.
- [ ] Keep any temporary/private FreePBX session broker blocked until authentication, expiry, revocation, CSRF, audit, redirects/cookies/WebSockets/CSP/X-Frame-Options, listener equivalence, and rollback are proven.

## P2 — DTMF provider response

Externally blocked pending provider response.

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

## Completed / do not reopen without new evidence

- [x] Edge1 public front door LIVE / ACCEPTED on 2026-08-19; canonical destination `https://ww.cx/time/`.
- [x] Edge1 front-door rollback/evidence preserved at `/var/backups/wwcx-edge1-front-door-approved-20260819T052836Z`.
- [x] Edge1 server-side bounded MCP Operator verified live on loopback.
- [x] Non-secret Secure MCP Tunnel host staging accepted; service intentionally disabled/inactive pending credential enrollment.
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
