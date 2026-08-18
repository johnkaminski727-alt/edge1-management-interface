# Unified Communications — Remaining Backlog

Date: 2026-08-18, Phase 28 closeout

This backlog contains only live/external work that remains after PR #427 delivered the functional local-native Mail correspondence software path. Repository functionality, live Edge1 acceptance, provider readiness, authentication-policy approval, and production authorization remain separate evidence layers.

## Completed repository/software work

- [x] Unified Communications convergence and readiness contracts.
- [x] Durable Messaging PostgreSQL implementation and prior live acceptance.
- [x] Messaging status/conversation reads and prepared-not-sent drafts.
- [x] Persistent loopback Communications workspace and authoritative Relay metadata feed.
- [x] Bounded Voice/SIP read-only functional acceptance.
- [x] Private MMS content-addressed quarantine foundation.
- [x] Fixed local `/usr/bin/clamscan` adapter and local clean/EICAR/failure/restart acceptance tooling.
- [x] Private Mail SQLite body/thread store with immutable per-record source authority.
- [x] Persist immutable Mail source scope (`synthetic`, `local_native`, `production_native`, legacy fail-safe scope).
- [x] Prevent synthetic correspondence from claiming or being upgraded to readable authority.
- [x] Implement local RFC822 native intake with canonical Message-ID, Date, In-Reply-To, References, bounded text/plain body and optional native/provider IDs.
- [x] Constrain runtime correspondence database selection to `/var/lib/wwcx-mail-room`.
- [x] Add bounded Mail AI individual-message/thread reads with local-vs-production source truth.
- [x] Add HMAC-authenticated loopback correspondence endpoints to the existing Mail gateway.
- [x] Require dedicated correspondence client ID `wwcx-private-ai`; existing website-admin authorization does not imply message-body access.
- [x] Add BigBird Mail repository facade and manifest with no send capability.
- [x] Add end-to-end local functional validation: RFC822 -> store -> API -> BigBird read + prepared-not-sent draft.
- [x] Pass exact-head repository CI on `88253f0c3c2839b2192cc1d9f723c92a79b293be`.
- [x] Merge Phase 28 implementation PR #427 as `e7d7fda638a4f69d68bf54cdebdbee9070143384`.

Exact-head implementation CI:

- Validate repository — run `32196436559` — PASS;
- Edge1 Operator Validation — run `32196436531` — PASS;
- Validate outbound mail suppression server — run `32196436670` — PASS.

## MMS live security runtime

Blocked by the absence of an authenticated Edge1 execution path in this session, not by missing repository implementation.

- [ ] Authenticate to Edge1 and verify host/principal/current `main`.
- [ ] Reinspect Messaging service identity, memory/swap, disk, scanner/signature packages, listeners and private-root candidates.
- [ ] Confirm/install a resource-safe local trusted scanner under established operator policy.
- [ ] Create/verify `/var/lib/wwcx-messaging-gateway/private-mms-quarantine` outside web roots with directories <=0700 and files <=0600 under the actual service identity.
- [ ] Run clean -> `scanned_clean_held`.
- [ ] Run EICAR -> `quarantined_malicious`.
- [ ] Run unavailable/timeout/error/non-verdict failure cases -> held.
- [ ] Run digest mismatch/integrity corruption/storage failure cases -> fail closed.
- [ ] Verify restart/re-open persistence.
- [ ] Verify no new public listener, adjacent UC service health and rollback viability.
- [ ] Capture protected evidence.

Quarantine release remains unauthorized throughout.

## Mail live local-native acceptance

The software path is functional and merged. Live Edge1 deployment remains unperformed because no authenticated execution connector is exposed.

- [ ] Verify live outbound Mail gateway service identity and current preparation-only runtime configuration.
- [ ] Create `/var/lib/wwcx-mail-room` under the reviewed service/intake ownership model with directory permissions no broader than 0700.
- [ ] Ingest local RFC822 fixtures using the reviewed local intake identity; verify DB no broader than 0600.
- [ ] Enable correspondence reads only after the private store contains `local_native` authoritative records.
- [ ] Verify authenticated loopback status/message/thread reads.
- [ ] Verify malformed/missing/synthetic IDs fail closed.
- [ ] Verify prompt-like content remains untrusted and cannot grant scopes/tools.
- [ ] Verify Mail gateway remains loopback-only and delivery/send remains disabled.
- [ ] Verify restart/re-open state and protected rollback evidence.

## BigBird live Mail registration

PR #427 deliberately left the deployed/base HMAC allowed-client policy unchanged. Adding `wwcx-private-ai` to the live allowed-client set is an **authentication-policy change** and requires separate explicit approval.

- [ ] Obtain explicit approval for the dedicated `wwcx-private-ai` HMAC client registration.
- [ ] Reuse the existing secret location/mechanism; never display or copy secret values into repository/evidence.
- [ ] Register only the least-privileged Mail status/correspondence/draft capabilities.
- [ ] Verify `wwcx-website-admin` remains rejected from correspondence endpoints.
- [ ] Validate missing-scope rejection, unsigned rejection, replay rejection and no-send/no-generic-execution boundaries.
- [ ] Record live acceptance and rollback.

Do not silently reuse the website-admin identity for BigBird merely to avoid the approval boundary.

## Production-native Mail source

This is separate from local software functionality.

- [ ] Identify/authorize an existing native mailbox/MTA/provider source with stable message IDs, thread IDs and real bodies if one exists.
- [ ] Preserve immutable `production_native` provenance.
- [ ] Perform bounded read-only acceptance before claiming provider-production correspondence readiness.

Current provider inventory does not prove the canonical provider-side mailboxes/source are provisioned. No provider credentials, routing, DNS or live mail changes are authorized by this backlog.

## Voice/SIP health freshness

- [ ] Optional: obtain a genuinely fresh read-only live interconnect health source if operational freshness is needed.
- [ ] Do not originate calls or modify routes/trunks/dialplans/carrier/emergency settings merely to change the displayed health state.

## Final readiness

- [ ] Set SMS/MMS `security_quarantine=security_ready` only after live scanner/private-root acceptance.
- [ ] Promote local Mail correspondence to live accepted only after Edge1 deployment tests.
- [ ] Promote provider-production Mail correspondence only after a production-native source is proven.
- [ ] Set `fresh_edge1_runtime_verified=true` only after intended safe-scope runtime requirements are genuinely complete or explicitly resolved with evidence.

## Separately controlled production work

- provider credentials/configuration;
- live SMS/MMS routing/transmission;
- live mail routing/transmission;
- SIP/carrier/emergency routing or dialplan mutation;
- production call origination;
- DNS/firewall/certificate/authentication-policy changes;
- number porting or STIR/SHAKEN;
- quarantine release;
- destructive/irreversible operations;
- provider financial/contractual/legal/regulatory actions.

## Durable recovery records

- `.agent/unified-communications.md`;
- `.agent/unified-communications-validation-20260818.md`;
- `.agent/unified-communications-validation-phase27-20260818.md`;
- `.agent/unified-communications-validation-phase28-20260818.md`;
- `config/communications/readiness-matrix-v1.json`;
- `config/communications/unified-communications.json`;
- `docs/communications/unified-communications-phase27-runtime-acceptance-20260818.md`;
- `docs/communications/unified-communications-phase28-live-acceptance-20260818.md`;
- `docs/handoff/unified-communications-phase28-20260818.md`.

No unchecked item above should be represented as complete without evidence for that specific layer.
