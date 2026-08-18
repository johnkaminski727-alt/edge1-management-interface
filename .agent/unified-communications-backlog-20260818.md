# Unified Communications — Remaining Backlog

Date: 2026-08-18

This backlog contains only work not completed by the safe repository/runtime convergence pass. Fresh Edge1 operator acceptance is complete for Messaging Gateway including durable PostgreSQL state, BigBird messaging capabilities, the bounded Mail AI adapter, the persistent loopback-only Communications workspace, and the authoritative Relay/NNTP canonical snapshot feed. Remaining items are kept explicit rather than inferred complete.

## Runtime verification

- [x] Run a fresh authenticated/operator-run read-only Edge1 acceptance pass for the safe available surfaces.
- [x] Confirm live Messaging Gateway `0.4.2`, BigBird `0.3.4-alpha.3`, Mail AI adapter bounded capabilities, and adjacent UC service active state.
- [x] Confirm Messaging Gateway and BigBird loopback listeners and verify the Communications workspace temporary listener rolls back cleanly.
- [x] Complete fresh functional Communications Relay acceptance by attaching and validating an authoritative metadata-only canonical snapshot.
- [ ] Complete fresh functional Voice/SIP acceptance beyond service-active evidence if required for final global runtime verification.
- [x] Install and accept the persistent loopback-only `wwcx-communications-workspace.service`.
- [x] Confirm and attach the authoritative canonical communications-event snapshot/feed source used by the persistent workspace.
- [x] Record live rollback/checkpoint evidence for Messaging Gateway, BigBird, Communications workspace, Relay snapshot activation, and Messaging PostgreSQL activation.
- [ ] Reconcile final safe-scope state and set `fresh_edge1_runtime_verified` true only after MMS security runtime, Mail correspondence, and any required fresh Voice/SIP acceptance are complete.

Phase 14J acceptance on 2026-08-18 confirmed a live 168-event Relay/NNTP canonical snapshot attached to the persistent workspace. The generator runs as `wwcx-comms:wwadmin`, the authoritative Relay database remains `0600 wwcx-comms:wwcx-comms`, the generated snapshot is `0640 wwcx-comms:wwadmin`, the workspace remains loopback-only and read-only, POST remains HTTP 405, and a 15-minute refresh timer is enabled. Rollback: `/tmp/edge1-uc-evidence-20260818T073658Z/rollback-relay-activation-20260818T103350Z.sh`.

Phase 18 acceptance on 2026-08-18 replaced volatile Messaging storage with the already-implemented PostgreSQL backend. PostgreSQL 15 is local Unix-socket only with no TCP listener and no database password, repository migrations were applied, the pre-restart in-memory event count was zero, `/readyz` now reports `storage: postgres`, PostgreSQL is enabled for reboot persistence, and the bounded rollback retains the installed data while restoring Messaging memory mode and stopping the cluster if needed. Rollback: `/tmp/edge1-uc-evidence-20260818T073658Z/rollback-messaging-postgres-20260818T111017Z.sh`.

Operational warning retained: approximately 1.5 GiB memory remained available after Phase 18, while the configured 1 GiB swap allocation remained almost fully consumed. No recent OOM activity was observed and PostgreSQL activation did not materially reduce available memory, but unnecessary broad service restarts should still be avoided.

## Messaging durability

- [x] Replace Messaging Gateway `storage: memory` with approved durable private PostgreSQL state.
- [x] Preserve current read-only/private-AI authorization boundaries and restart-state semantics.
- [x] Add rollback, failure handling, reboot persistence, and live post-restart acceptance.

Messaging durability is no longer a blocker. The accepted runtime uses the existing repository `PostgresEventStore`, peer-authenticated Unix-socket access as the `wwadmin` OS identity, repository migrations `0001_initial.sql` and `0002_control_state.sql`, no PostgreSQL TCP listener, and no database password.

## Mail correspondence

- [ ] Identify and explicitly authorize the authoritative native Mail Room correspondence/thread source for `mail.correspondence.read`.
- [ ] Build a sanitized bounded adapter that preserves native IDs, thread relationships, authorization boundaries, and provenance.
- [ ] Validate that outbound audit metadata is never substituted for correspondence bodies/history.

Freshly accepted and not blocked by the above:

- [x] `mail.status.read` local bounded status behavior.
- [x] `mail.draft.prepare` prepared-not-sent behavior with no send/mutation authority.

## MMS quarantine runtime

- [ ] Attach private quarantine storage with bounded retention and access policy.
- [ ] Attach a trusted malware/media scanner behind the fail-closed scanner callback boundary.
- [ ] Add operational readiness/health evidence for storage and scanner degradation.
- [ ] Design a separately authorized, audited release workflow; do not grant release to Private AI.

Fresh inspection found no installed trusted scanner and no attached private quarantine storage. The live Messaging Gateway quarantine projection remains fail-closed and release remains unauthorized.

## Voice/SIP fresh acceptance

- [ ] Decide whether final global safe-scope completion requires a fresh functional Voice/SIP read acceptance beyond historical `telephony.read` evidence.
- [ ] If required, validate only existing read-only/local status and historical-record surfaces without originating calls or changing routes, trunks, dialplans, emergency calling, or carrier configuration.

Current native CDR/CEL tables were observed empty during the fresh 2026-08-18 pass, so no fabricated call records should be introduced merely to satisfy acceptance.

## Provider / production activation

These remain outside standing safe repository authority and require separate explicit approval where applicable:

- [ ] provider credentials/configuration;
- [ ] live SMS/MMS routing and transmission;
- [ ] live mail transmission where not separately authorized;
- [ ] SIP/carrier route or dialplan mutation;
- [ ] production call origination;
- [ ] emergency calling changes;
- [ ] number porting;
- [ ] STIR/SHAKEN changes;
- [ ] DNS/firewall/certificate/authentication-policy changes;
- [ ] quarantine release;
- [ ] provider contractual or financial actions.

## Product follow-through

- [ ] Populate evidence-backed cross-channel identity links only when authoritative evidence exists.
- [x] Replace the intentionally empty workspace input with an approved bounded runtime aggregation feed from an authoritative native channel source (Communications Relay/NNTP).
- [ ] Add additional authoritative native channel adapters only as their source stores and privacy/security rules are explicitly established.
- [ ] Run accessibility/browser acceptance on the persistently deployed Communications workspace if/when an authenticated browser route is approved.

## Durable fresh acceptance records

See:

- `docs/communications/unified-communications-live-acceptance-20260818.md`;
- `docs/communications/unified-communications-relay-snapshot-live-acceptance-20260818.md`;
- `docs/communications/unified-communications-messaging-postgres-live-acceptance-20260818.md`;
- `.agent/unified-communications-validation-20260818.md`.

No item above should be represented as complete until evidence exists for that specific layer.
