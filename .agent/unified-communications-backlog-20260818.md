# Unified Communications — Remaining Backlog

Date: 2026-08-19, approved safe-scope live completion achieved

The previously pending Edge1 MMS, Mail Room, and BigBird Mail live-acceptance work is complete. Repository functionality, live Edge1 acceptance, provider-production readiness, and production traffic authorization remain separate evidence layers.

Approval record: `docs/communications/unified-communications-safe-scope-approval-20260819.md`.
Live acceptance record: `docs/communications/unified-communications-live-acceptance-20260819.md`.

## Completed repository/software work

- [x] Unified Communications convergence and readiness contracts.
- [x] Durable Messaging PostgreSQL implementation and prior live acceptance.
- [x] Messaging status/conversation reads and prepared-not-sent drafts.
- [x] Persistent loopback Communications workspace and authoritative Relay metadata feed.
- [x] Bounded Voice/SIP read-only functional acceptance.
- [x] Private MMS content-addressed quarantine foundation.
- [x] Fixed local `/usr/bin/clamscan` adapter and clean/EICAR/failure/restart acceptance tooling.
- [x] Private Mail SQLite body/thread store with immutable per-record source authority/scope.
- [x] Local RFC822 native intake with bounded `text/plain` persistence and explicit threading.
- [x] Runtime correspondence database constrained to `/var/lib/wwcx-mail-room`.
- [x] HMAC-authenticated loopback correspondence endpoints requiring exact client `wwcx-private-ai`.
- [x] BigBird Mail repository facade and manifest with no send capability.
- [x] End-to-end repository validation and exact-head CI.
- [x] Safe-scope authentication-policy/deployment approval.
- [x] PR #444 fixed private MMS intermediate-directory permissions.
- [x] PR #445 wired correspondence methods through the actual Mail runtime application.

## MMS live security runtime

- [x] Authenticate to Edge1 and verify host/principal/current `main`.
- [x] Reinspect Messaging service identity, memory/swap, disk, scanner packages, listeners and private-root candidates.
- [x] Install resource-safe command-line ClamAV/signature tooling without `clamav-daemon`.
- [x] Create `/var/lib/wwcx-messaging-gateway/private-mms-quarantine` outside web roots.
- [x] Enforce all quarantine directories at `0700` and files at `0600`.
- [x] Run clean -> `scanned_clean_held`.
- [x] Run EICAR -> `quarantined_malicious`.
- [x] Verify fail-closed/held semantics and no automatic release.
- [x] Verify restart/re-open persistence.
- [x] Verify no ClamAV daemon listener and no new public UC management listener.
- [x] Capture protected evidence.

Quarantine release remains unauthorized.

Maintenance warning: Debian currently provides ClamAV 1.4.3 while freshclam reported upstream recommendation 1.4.6. Signature update and live scanning acceptance succeeded; track routine package updates separately.

## Mail live local-native acceptance

- [x] Verify live outbound Mail gateway service identity and preparation-only runtime configuration.
- [x] Create `/var/lib/wwcx-mail-room` owner `wwcx-mail-gateway`, mode `0700`.
- [x] Ingest local RFC822 root/reply fixtures under reviewed local intake identity.
- [x] Verify SQLite DB mode `0600`, two authoritative `local_native` records and explicit threading.
- [x] Enable correspondence reads against the private store only after native records exist.
- [x] Add dedicated `wwcx-private-ai` HMAC client while retaining website-admin isolation.
- [x] Verify unsigned and website-admin correspondence access are rejected.
- [x] Verify private-ai status/message/thread reads.
- [x] Verify malformed ID and nonce replay fail closed.
- [x] Verify prompt-like body remains untrusted and cannot grant scope/tool authority.
- [x] Verify provider remains `none`, `production_provider_ready=false`, external delivery false and send endpoint disabled.
- [x] Verify restart/service health/listener boundaries and retain rollback evidence.

## BigBird live Mail registration

- [x] Reuse existing HMAC secret mechanism without displaying, rotating or committing secret material.
- [x] Deploy reviewed `integrations/bigbird_mail` package into the BigBird deployment tree.
- [x] Register only `mail.status.read`, `mail.correspondence.read`, and `mail.draft.prepare`.
- [x] Keep all three registry-classified read-only; draft remains `prepared_not_sent`.
- [x] Validate dedicated gateway authentication, status/message/thread reads and untrusted-content boundary.
- [x] Validate internal-viewer + explicit Mail scope authorization.
- [x] Validate registered-user and missing-scope rejection.
- [x] Validate BigBird Mail prepared-not-sent draft and external delivery false.
- [x] Restart only BigBird and verify healthy loopback service.
- [x] Record protected rollback/evidence.

BigBird live deployment accepted version: `0.3.5-alpha.1`.

## Final shared regression

- [x] Messaging Gateway active and healthy.
- [x] Outbound Mail Gateway active and healthy.
- [x] BigBird active and healthy.
- [x] Communications workspace active on loopback; POST rejected HTTP 405.
- [x] Communications Relay active.
- [x] Asterisk active.
- [x] Kamailio active.
- [x] Telephony console/analytics health passed; analytics POST rejected HTTP 405.
- [x] No new public BigBird/Mail/Messaging management listener.
- [x] No OOM-killer evidence in acceptance window.
- [x] Edge1 repository clean and synchronized at accepted head.

Observed but out of UC scope: `bigbird-edge1-connector-maintenance.service` and `bigbird-edge1-connector.service` were failed in the generic failed-unit listing. BigBird/UC runtime acceptance did not depend on them; track separately.

## Final readiness

- [x] SMS/MMS `security_quarantine=security_ready` based on live scanner/private-root acceptance.
- [x] Promote local Mail correspondence to live accepted.
- [x] Promote BigBird Mail status/correspondence/draft capabilities to accepted-live.
- [x] Set `fresh_edge1_runtime_verified=true` for the intended approved safe-scope UC requirements.

## Optional/separate future work

### Production-native Mail source

- [ ] Read-only discover an already-existing native mailbox/MTA/provider source with stable message IDs, thread IDs and real bodies if available without new credentials/provider activation.
- [ ] Preserve immutable `production_native` provenance if such an already-authorized source is connected.
- [ ] Perform bounded read-only acceptance before claiming provider-production correspondence readiness.

Provider-native Mail is **not required** for the completed local safe-scope objective. No new provider credentials, routing, DNS or live mail changes are implied.

### Voice/SIP external-health freshness

- [ ] Optional: obtain a genuinely fresh read-only carrier/interconnect health source if external operational freshness is needed.
- [ ] Do not originate calls or modify routes/trunks/dialplans/carrier/emergency settings merely to change the displayed health state.

### Unrelated Edge1 connector services

- [ ] Separately inspect the failed `bigbird-edge1-connector.service` and `bigbird-edge1-connector-maintenance.service` if connector lifecycle health is desired. Do not conflate those units with the accepted BigBird AI Gateway UC runtime.

## Still separately controlled and not required for this completion

- live SMS/MMS routing/transmission;
- live mail routing/transmission;
- SIP/carrier/emergency routing or dialplan mutation;
- production call origination;
- DNS/firewall/certificate/public-listener changes outside the reviewed private design;
- number porting or STIR/SHAKEN;
- credential disclosure or rotation;
- quarantine release;
- destructive/irreversible operations;
- provider financial/contractual/legal/regulatory actions.

## Durable recovery records

- `.agent/unified-communications.md`;
- `.agent/unified-communications-backlog-20260818.md`;
- `.agent/unified-communications-validation-phase28-20260818.md`;
- `config/communications/readiness-matrix-v1.json`;
- `config/communications/unified-communications.json`;
- `docs/communications/unified-communications-live-acceptance-20260819.md`;
- `docs/handoff/unified-communications-live-closeout-20260819.md`.
