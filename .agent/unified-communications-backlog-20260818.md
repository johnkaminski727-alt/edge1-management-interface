# Unified Communications — Remaining Backlog

Date: 2026-08-18, Phase 27 reconciliation

This backlog contains only work still requiring evidence after the safe repository implementation pass. It distinguishes repository completion, Edge1 deployment, live functional acceptance, provider readiness, and production authorization.

## Completed safe-scope foundations

- [x] Unified Communications convergence contracts, identity/readiness model, search/correlation core.
- [x] Durable Messaging Gateway PostgreSQL state and fresh read-only acceptance.
- [x] Messaging status/conversation reads and local prepared-not-sent drafts.
- [x] Mail status and local prepared-not-sent draft behavior.
- [x] Persistent loopback-only Communications workspace.
- [x] Authoritative Communications Relay/NNTP canonical metadata snapshot and refresh.
- [x] Fresh bounded Voice/SIP read-only functional acceptance.
- [x] Repository-side private MMS content-addressed quarantine storage foundation.
- [x] Repository-side narrow `TrustedMediaScanner` contract.
- [x] Phase 27 concrete fixed-path local `/usr/bin/clamscan` adapter with bounded failure handling.
- [x] Phase 27 local-only synthetic clean/EICAR/restart MMS acceptance probe.
- [x] Phase 27 private bounded SQLite Mail correspondence-store foundation.
- [x] Phase 27 synthetic Mail message/thread persistence and read validation.

## MMS trusted scanner and private quarantine runtime

Repository implementation is complete enough for live acceptance, but live Edge1 evidence is still missing because this session had no authenticated Edge1 execution connector.

- [ ] Establish authenticated Edge1 execution and verify host/principal.
- [ ] Re-check current `main`/runtime revision and Messaging service identity before mutation.
- [ ] Inspect current memory/swap, installed scanners/signatures, private data roots, ownership/modes, filesystems/free space, packages, and security/quarantine infrastructure.
- [ ] Confirm whether `/usr/bin/clamscan` with a usable local signature database already exists.
- [ ] If no trusted scanner exists, install/approve one only if authenticated operator policy and host resources permit it. Avoid adding a resident public/listening service merely for convenience; the repository adapter supports one-shot local `clamscan`.
- [ ] Establish `/var/lib/wwcx-messaging-gateway/private-mms-quarantine` under the actual Messaging service identity, outside any web document root, with root/subdirectories no broader than `0700` and blobs/metadata `0600`.
- [ ] Run local synthetic clean -> `scanned_clean_held` acceptance.
- [ ] Run local generated EICAR -> `quarantined_malicious` acceptance if the chosen scanner supports EICAR.
- [ ] Validate scanner unavailable -> held.
- [ ] Validate scanner timeout/error/non-verdict -> held.
- [ ] Validate digest mismatch -> rejected/held.
- [ ] Validate corrupted blob/integrity failure -> held.
- [ ] Validate storage/disk-full failure -> no success claim.
- [ ] Validate restart/re-open preserves held records/blobs.
- [ ] Verify no public scanner/quarantine listener appears and adjacent UC services remain healthy.
- [ ] Capture rollback/evidence outside the repository.
- [ ] Keep quarantine release unavailable to Private AI and unavailable from the tested path.

Runtime procedure: `docs/communications/unified-communications-phase27-runtime-acceptance-20260818.md`.

## Mail correspondence

The repository now has a bounded persisted store/read foundation, so the missing work is specifically the **authoritative native source and live read-only acceptance**.

- [x] Confirm outbound audit metadata is not an authoritative correspondence source.
- [x] Confirm `mail_threading.py` correlation metadata is not a body/thread-history store.
- [x] Confirm the disabled inbound hub does not persist raw messages/body previews/attachments.
- [x] Implement private persisted message/thread storage preserving canonical Message-ID, provider IDs, explicit thread relationships, provenance, untrusted-content markers, and bounded sizes.
- [x] Validate the store using local synthetic correspondence with no send/routing authority.
- [ ] Explicitly select and authorize one real native source: reviewed local MTA/Mail Room intake or an authorized native mailbox/provider connector.
- [ ] Prove the selected source supplies actual message bodies plus stable native message/thread IDs.
- [ ] Connect that source to the store/read adapter without enabling production send/routing authority.
- [ ] Perform bounded live read-only acceptance with missing/ambiguous IDs failing closed and prompt-like message content unable to grant scopes/tools.
- [ ] Only then enable/advertise `mail.correspondence.read` for that authorized source.

Current provider inventory still does not prove the canonical provider-side mailboxes are provisioned. Production inbound routing remains blocked.

## Voice/SIP operational-health freshness

Fresh bounded functional read-only acceptance is complete. Current live interconnect health is **unknown**, not freshly proven degraded: the Phase 19 API surfaced a repository status snapshot last checked 2026-07-20.

- [ ] If operational-health freshness is needed, use a separately approved read-only live source/probe.
- [ ] Do not originate calls or modify routes/trunks/dialplans/emergency/carrier settings merely to clear the unknown state.

## Final readiness reconciliation

- [ ] Set SMS/MMS `security_quarantine=security_ready` only after live scanner/root acceptance passes.
- [ ] Resolve the Mail correspondence source gap with real source evidence or an explicit documented external blocker.
- [ ] Set `fresh_edge1_runtime_verified=true` only after every intended safe-scope UC runtime requirement is genuinely complete or explicitly resolved with evidence.

That flag must never imply carrier readiness, provider credentials, DNS readiness, live mail delivery, emergency calling readiness, production authorization, or quarantine release authority.

## Provider / production activation remains separately controlled

- [ ] provider credentials/configuration;
- [ ] live SMS/MMS routing/transmission;
- [ ] live mail routing/transmission;
- [ ] SIP/carrier route or dialplan mutation;
- [ ] production call origination;
- [ ] emergency-calling changes;
- [ ] number porting;
- [ ] STIR/SHAKEN actions;
- [ ] DNS/firewall/certificate/authentication-policy changes;
- [ ] quarantine release;
- [ ] provider contractual/financial/legal/regulatory actions.

## Durable recovery records

- `.agent/unified-communications.md`
- `.agent/unified-communications-validation-20260818.md`
- `.agent/unified-communications-validation-phase27-20260818.md`
- `config/communications/readiness-matrix-v1.json`
- `docs/communications/unified-communications-phase27-runtime-acceptance-20260818.md`
- `docs/handoff/unified-communications-phase27-20260818.md`

No unchecked item above should be represented as complete until evidence exists for that specific layer.
