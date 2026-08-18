# WW.CX Unified Communications — Phase 28 Handoff

Date: 2026-08-18
Repository: `johnkaminski727-alt/edge1-management-interface`
Primary private host: `edge1.ww.cx`
Implementation PR: #427
Reviewed implementation head: `88253f0c3c2839b2192cc1d9f723c92a79b293be`
Implementation merge: `e7d7fda638a4f69d68bf54cdebdbee9070143384`

## Functional software delivered

Phase 28 delivered and merged a functioning local-native Mail correspondence subsystem rather than another storage-only foundation.

End-to-end repository/local acceptance path:

`RFC822 -> local native intake -> private persisted message/thread store -> authenticated loopback correspondence API -> BigBird Mail facade -> mail.correspondence.read`

The same bounded facade retains prepared-not-sent draft functionality and has no send method.

## Mail implementation

### Source and persistence

- `server/mail_local_rfc822_source.py` parses bounded local RFC822 mail without network activity.
- `tools/mail_local_intake.py` is the operator-facing local intake path and constrains runtime storage under `/var/lib/wwcx-mail-room`.
- `server/mail_correspondence_store.py` persists message bodies, canonical/native IDs, explicit thread relationships and immutable source/scope/authority provenance.
- Synthetic records remain non-authoritative and cannot be relabeled by reader configuration.
- Read-only consumers use SQLite `mode=ro`.
- API projections do not disclose the private database path.

### Read API

`server/mail_ai_adapter.py` supports bounded message/thread reads only when persisted provenance is authoritative and scoped `local_native` or `production_native`.

`server/outbound_mail_gateway_server.py` exposes authenticated loopback correspondence endpoints behind the existing replay-protected HMAC mechanism.

Correspondence endpoints additionally require exact client ID `wwcx-private-ai`; an already-authorized website-admin HMAC client does not inherit body-read permission.

### BigBird repository integration

- `integrations/bigbird_mail/client.py` — loopback-only HMAC client;
- `integrations/bigbird_mail/tools.py` — status/correspondence/draft facade with repeated untrusted/no-send/provenance checks;
- `integrations/bigbird-mail/tool-manifest.json` — `mail.status.read`, `mail.correspondence.read`, `mail.draft.prepare`; explicitly forbids mail send, route modification, generic execution and quarantine release.

The base production HMAC allowed-client policy remains unchanged. `wwcx-private-ai` was added only to the isolated integration-test config for functional proof.

## CI and review

Exact-head checks on `88253f0c3c2839b2192cc1d9f723c92a79b293be` all passed before merge:

- Validate repository — `32196436559`;
- Edge1 Operator Validation — `32196436531`;
- Validate outbound mail suppression server — `32196436670`.

No review threads remained before merge.

Manual review found and fixed a potential privilege inheritance issue before merge: existing HMAC clients could otherwise have reached the new endpoints once correspondence reads were enabled. The final implementation requires the dedicated client ID, and `tests/validate_mail_correspondence_client_isolation.py` protects that boundary.

## MMS status

The Phase 27 MMS implementation remains repository-ready:

- private content-addressed quarantine storage;
- SHA-256 integrity checks;
- fail-closed scan states;
- fixed `/usr/bin/clamscan` adapter;
- local clean/EICAR/error/restart acceptance tooling;
- no automatic quarantine release.

It is not yet live-accepted on Edge1 in this session because no authenticated Edge1 execution connector is exposed.

## Live-host boundary

No live Phase 28 Edge1 mutation was performed or claimed.

This session lacks both an exposed Edge1 Live Shell connector and a usable local SSH identity. Therefore these remain live acceptance tasks rather than software-design tasks:

- create/verify the live private MMS quarantine root and scanner state;
- run MMS clean/EICAR/failure/restart acceptance;
- create/verify `/var/lib/wwcx-mail-room` with actual live service/intake identities;
- ingest local RFC822 fixtures live;
- enable and exercise live local-native correspondence reads;
- verify service restarts, listeners, logs, permissions and rollback;
- register/accept BigBird Mail tools after authentication-policy approval.

Exact procedure: `docs/communications/unified-communications-phase28-live-acceptance-20260818.md`.

## Explicit approval still required

### BigBird HMAC client registration

Adding `wwcx-private-ai` to the deployed HMAC allowed-client set changes authentication policy. The governing task explicitly reserves authentication-policy changes for separate approval.

Do not bypass this by reusing the website-admin identity.

### Provider-native correspondence

The local-native path is functional and accurately reports `production_provider_ready=false`. A provider/native mailbox source is still unproven. Only an explicitly authorized real source should produce `production_native` provenance.

No provider credentials, DNS, MX, forwarding, mail routing or live email changes are implied by Phase 28.

## Shared-system state

Existing accepted live states remain unchanged unless fresh Edge1 evidence later proves otherwise:

- Messaging/PostgreSQL — runtime-ready from prior acceptance; PR #426 durable outbound queue now exists on main but Phase 28 did not live-operate it;
- BigBird — existing Messaging/communications/telephony read-only capabilities remain previously accepted; Phase 28 Mail tools are merged but not live-registered;
- Communications workspace/Relay — previously runtime-ready and loopback-only with authoritative Relay metadata feed;
- Voice/SIP — bounded read-only acceptance remains valid; current external interconnect health remains unknown rather than freshly degraded/healthy.

## Readiness truth

- local Mail software functionality: **complete and merged**;
- repository CI: **green**;
- local provider-independent correspondence source: **functional**;
- live Edge1 Phase 28 acceptance: **not executed; execution connector unavailable**;
- live BigBird Mail registration: **blocked on explicit authentication-policy approval plus Edge1 access**;
- production-native Mail source: **unproven/blocked externally**;
- MMS live scanner/private-root acceptance: **not executed; Edge1 access unavailable**;
- production communication authority: **unchanged/blocked**;
- `fresh_edge1_runtime_verified`: **false**.

## Recovery point

Continue from:

- `.agent/unified-communications.md`;
- `.agent/unified-communications-backlog-20260818.md`;
- `.agent/unified-communications-validation-phase28-20260818.md`;
- `config/communications/readiness-matrix-v1.json`;
- `config/communications/unified-communications.json`;
- `docs/communications/unified-communications-phase28-live-acceptance-20260818.md`;
- this handoff.

Do not reconstruct provider/live state from assumptions. Inspect Edge1 and current main first when an authenticated execution path becomes available.
