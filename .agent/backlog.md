# Backlog

## Communications Relay / upstream NNTP / News Reader closeout

- [x] Accept private loopback Communications Relay service.
- [x] Accept founder/local relay identity.
- [x] Accept local `wwcx-bootstrap` and `edge1-repository` automatic ingestion.
- [x] Accept `eternal.comp.lang.python` -> `usenet.comp.lang.python` over TLS reader mode.
- [x] Accept `eternal.news.admin.peering` -> `usenet.news.admin.peering` over TLS reader mode.
- [x] Preserve provenance-aware accounting and zero duplicate external source IDs at acceptance.
- [x] Accept private News Reader v2 with search, exact source filters, pagination, threaded/flat views and HTTP 405 mutation enforcement.
- [x] Reconcile exact validated News Reader blobs into repository history through PR #341.
- [x] Close PR #337 as superseded development history.
- [x] Reconcile durable Communications Relay state through PR #342.
- [x] Create dated second-source and News Reader v2 acceptance records.
- [x] Reconcile living architecture, ingestion, validation, News Reader and runbook documentation.
- [x] Create sanitized archive closeout and protected-evidence source ledger.
- [ ] Resolve the exact protected News Reader v2 deployment-evidence directory on Edge1.
- [ ] Generate a read-only SHA-256 inventory for every retained Communications Relay evidence file.
- [ ] Capture metadata/hash for live config and SQLite without committing private objects.
- [ ] Confirm Eternal September credential contents are excluded from the archive payload.
- [ ] Reconcile retained, unavailable, exact-duplicate and error totals.
- [ ] Rerun the inventory and require idempotent totals.
- [ ] Update the closeout with the final manifest path and SHA-256.
- [ ] Merge the final documentation-only archive-seal update.

Archive closeout:

`docs/archive/edge1-comms-relay-news-reader-closeout-20260817.md`

Production checkout discipline: do not move the accepted relay/News Reader checkout to current remote `main` merely for archive or documentation reconciliation.

## Completed live phases

- [x] Security Correlation and Network Defense deployed and accepted.
- [x] Suricata drill-down, caching, normalization, and enrichment deployed.
- [x] Network Defense freshness threshold activated and accepted at `600` seconds.
- [x] Verified enforcement count remained `1` before and after activation.
- [x] DNS remains `not_staged`; DNS enforcement remains false.
- [x] Timer state and traffic controls remained unchanged.
- [x] Asterisk updated from `22.8.2` to `22.10.1` with zero active calls and protected rollback evidence.
- [x] Asterisk restarted and validated; Kamailio remained active.
- [x] Offline CAP-CP/EBS alerting laboratory installed under `/opt/wwcx-alerting-lab`.
- [x] Installed synthetic CAP-CP structural and lifecycle smoke tests passed.
- [x] No CAP feed, `Actual` alert handling, alert dialplan, call/page route, tone transmission, or public delivery path was enabled.

## Completed repository phases

- [x] Protected Suricata retention runtime and closeout through PRs #138-139.
- [x] Minimized public-summary route, CSP, staging runtime, and closeout through PRs #140-145.
- [x] Authenticated detailed-operations browser/session boundary and closeout through PRs #146-147.
- [x] Restricted-artifact migration manifest and closeout through PRs #148-149.
- [x] Security-boundary live inventory bundle merged through PR #151 as `85d9a9cb43e5ca4dd09f2d955b00997ef28e2cf0`.
- [x] Test-only EBS and CAP-CP compatibility foundation merged through PR #157 as `7456304d41063075be15ff894af815877dd8a554`.
- [x] Alerting continuity state merged through PR #159 as `03d219e853bd8a373cd9d0503c45579901615017`.

## DTMF provider evidence and response tracking

Tracker:

```text
.agent/dtmf-provider-response-tracker.md
```

- [x] Accept local Asterisk DTMF readiness and the offline 16-key probe.
- [x] Create the sanitized provider-public evidence intake and capability matrix gate.
- [x] Record only the documented account-level in-band fallback; keep unsupported capabilities `unknown`.
- [x] Send the nine-question provider technical escalation.
- [x] Exhaust provider-controlled public documentation without promoting unsupported claims.
- [x] Add the technical-response schema, pending example, validator, tests, and response-classification procedure through PR #250 as `faaf7b04c5fd3648b42b9266eb2cf5fea0f2a5a7`.
- [x] Synchronize and validate the response-intake package on Edge1.
- [x] Preserve protected evidence at `/var/lib/wwcx-deployment-evidence/repository-metadata-repair/20260801T180347Z/dtmf-provider-response-intake-sync-20260801T210156Z`.
- [x] Verify final evidence manifest `fe414802b5e52089673e3231693fbc1cb89c615c65e1450d670d77bcb03d7db4`.
- [x] Merge the durable Edge1 acceptance record through PR #251 as `d89cbb06d5ecd171e67c1a281beb58ef16a1f24c`.
- [x] Keep `response_state=pending`, `matrix_update_allowed=false`, and `live_test_authorized=false`.
- [ ] Receive a direct provider technical response.
- [ ] Retain the original response in the restricted mailbox and create only a sanitized response worksheet.
- [ ] Classify all nine answers by exact service scope and evidence strength.
- [ ] Leave ambiguous, indirect, best-effort, configuration-only, and test-required claims out of the carrier matrix.
- [ ] Run the response, privacy, provider-evidence, cross-record matrix, and repository validators before any matrix update.
- [ ] Require separate explicit authorization before any controlled call or DTMF transmission.

Current provider capability state:

```text
inband=documented
rfc4733=unknown
rfc4733_event_range=unknown
sip_info=unknown
extended_abcd=unknown
carrier_interoperability=partially-documented
response_state=pending
provider_reply_received=false
matrix_update_allowed=false
live_test_authorized=false
```

## Alerting compatibility foundation

- [x] Add bounded CAP 1.2 and CAP-CP structural validation.
- [x] Block `Actual` alerts by default.
- [x] Add one-subject-event, language, event-reference, and location checks.
- [x] Add duplicate, replay, freshness, Update, and Cancel lifecycle checks.
- [x] Add receive-only legacy EBS 853/960 Hz WAV detection.
- [x] Add nine targeted compatibility tests and a mandatory repository CI entrypoint.
- [x] Add a deny-by-default offline laboratory policy.
- [x] Add a read-only Asterisk readiness audit.
- [x] Add a guarded Asterisk 22 updater with simulation, active-call gate, backup, restart, and evidence capture.
- [x] Add an offline-only installer that creates no service, listener, feed, dialplan, or call route.
- [x] Pass `Validate repository` run 692.
- [x] Pass `Edge1 Operator Validation` run 524.
- [x] Pass `WW.CX interconnect staging validation` run 50.
- [x] Merge through PR #157 as `7456304d41063075be15ff894af815877dd8a554`.
- [x] Pull merged `main` on Edge1 and confirm the accepted continuity merge is present.
- [x] Run the read-only Asterisk alerting readiness audit.
- [x] Run and review the guarded Asterisk package simulation.
- [x] Apply and validate the Asterisk `22.10.1` update with zero active calls and protected rollback evidence.
- [x] Run the offline alerting-lab installer dry-run.
- [x] Install the offline tools without enabling networking or delivery.
- [x] Record protected evidence at `asterisk-security-update/20260731T233728Z` and `alerting-lab-install/20260731T233821Z`.
- [x] Add a read-only follow-up audit for transport visibility, boot persistence, and TCP `8089` exposure.
- [ ] Run the warning follow-up audit on Edge1 and record its evidence.
- [ ] Reconcile why `pjsip show transports` reports no objects while Asterisk owns UDP `127.0.0.1:5061`.
- [ ] Verify Asterisk boot persistence from SysV startup links and generated systemd behavior before any enablement change.
- [ ] Verify TCP `8089` TLS identity, authentication, firewall reachability, and operational need before any listener change.
- [ ] Obtain written authority and trust details before connecting any CAP-CP source.
- [ ] Implement persistent issuer trust, signatures where required, replay state, reference lists, geographic policy, bilingual rendering, accessibility, and audit controls before any delivery adapter.
- [ ] Keep `Actual` alert processing, Asterisk call/page delivery, tone generation, carrier routing, and public compatibility claims blocked pending separate authorization and conformance review.

## Security-boundary live inventory bundle

- [x] Record the exact four-program authorization and immutable guardrails without secrets.
- [x] Add clean-`main`, root, command, and authorization preflight gates.
- [x] Capture host, principal, capacity, repository revision, listeners, and relevant service state.
- [x] Capture redacted unit definitions and Apache syntax/vhost/module readiness.
- [x] Hash Apache configuration without copying configuration contents.
- [x] Generate exact JSON path/SHA-256/mode/byte inventory for the detailed public tree.
- [x] Report symlink and non-regular-file anomalies.
- [x] Reconcile live inventory against the merged migration manifest and access policy.
- [x] Preserve unknown artifacts for review and report missing known artifacts.
- [x] Capture anonymous local/public route and security-header matrices without credentials or cookie values.
- [x] Capture metadata-only candidate-root, audit-log, and retention-tree inventories.
- [x] Add evidence redactor and synthetic functional/static safety tests.
- [x] Add operator runbook, audit register, and continuity records.
- [x] Pass exact-head `Validate repository` run 662.
- [x] Pass exact-head `Edge1 Operator Validation` run 494.
- [x] Confirm 11 changed files, zero-behind state, mergeability, and zero unresolved review threads.
- [x] Merge through PR #151 as `85d9a9cb43e5ca4dd09f2d955b00997ef28e2cf0`.
- [ ] Run the merged script through an approved authenticated Edge1 path.
- [ ] Record the exact protected evidence directory and reconciliation counts.

## Post-inventory implementation sequence

- [ ] Reconcile every unknown, missing, prefix-contained, duplicate, stale, historical, and operator-maintained artifact.
- [ ] Verify an actually available approved identity provider and Apache adapter without placing secrets in Git or chat.
- [ ] Build a restricted release without changing the source tree.
- [ ] Stage and accept authenticated `/edge1-ops/` before anonymous withdrawal.
- [ ] Install and accept minimized public-summary staging.
- [ ] Install and accept protected Suricata retention.
- [ ] Archive the detailed public tree and perform the minimized public cutover only after authenticated equivalence succeeds.
- [ ] Confirm anonymous detailed routes are withdrawn, authenticated routes remain functional, listeners remain unchanged, and rollback is not required.

## Hard boundaries

- Never place credentials, client secrets, password hashes, tokens, cookies, private keys, or raw alert contents in Git or evidence.
- Never modify DNS, Unbound, RPZ, nftables, firewall rules, routing, IDS rules, reputation lists, certificates, or production traffic under this program without explicit authorization and validation.
- Never connect an alert feed, accept `Actual` alerts, originate calls/pages, generate or transmit alert tones, or claim Alert Ready/NPAS/EAS/EBS certification without separate authority and conformance evidence.
- Never delete retained status, releases, reports, incidents, history, audit, or deployment evidence.
- Roll back immediately if authentication, route isolation, public minimization, service health, data integrity, listener equivalence, PBX restart, or package-version validation fails.
