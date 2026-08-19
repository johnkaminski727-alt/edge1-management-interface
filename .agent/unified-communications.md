# Unified Communications — Current State

Last reconciled: 2026-08-19, safe-scope completion approval recorded
Repository: `johnkaminski727-alt/edge1-management-interface`
Phase 28 implementation PR: #427
Reviewed implementation head: `88253f0c3c2839b2192cc1d9f723c92a79b293be`
Phase 28 implementation merge: `e7d7fda638a4f69d68bf54cdebdbee9070143384`
Safe-scope approval record: `docs/communications/unified-communications-safe-scope-approval-20260819.md`
Global `fresh_edge1_runtime_verified`: **false**

## Current truth

WW.CX Communications remains read-only/non-sending by default. Phase 28 delivered and merged a functional local-native Mail correspondence software path while preserving production traffic, provider, credential, and quarantine-release boundaries.

The merged functional chain is:

`local RFC822 file -> bounded local-native parser -> private SQLite message/thread store -> authenticated loopback Mail API -> BigBird Mail facade -> mail.correspondence.read`

On 2026-08-19 the user explicitly approved the remaining **safe-scope completion work**, including bounded Edge1 deployment, package installation when required for the trusted local scanner, private storage creation, directly affected service restarts, and the exact authentication-policy change required to add dedicated Mail HMAC client `wwcx-private-ai` and register least-privileged BigBird Mail tools.

That approval clears the previously documented human-approval blocker. It does not itself constitute live execution or live acceptance evidence.

No current project state grants live Mail send, live SMS/MMS, call origination, route/trunk/dialplan mutation, provider credentials, quarantine release, destructive operations, or new public management exposure.

## Repository and CI state

Phase 28 began from `main` `9711461125a73f013b0f0a09347a6b1d1105eb5f`, which included PR #426's fail-closed durable outbound Messaging queue. PR #427 merged the Phase 28 implementation as `e7d7fda638a4f69d68bf54cdebdbee9070143384` after exact-head validation passed on `88253f0c3c2839b2192cc1d9f723c92a79b293be`:

- Validate repository — run `32196436559` — PASS;
- Edge1 Operator Validation — run `32196436531` — PASS;
- Validate outbound mail suppression server — run `32196436670` — PASS.

Phase 28 closeout PR #430 later merged as `bb34c144ab9375b4ee951834e270f794404fb27f`. Subsequent parallel work advanced `main`, including a guarded Edge1 Live Shell MCP connector. Parallel work must be preserved.

## Functional local Mail correspondence

### Local native source

`server/mail_local_rfc822_source.py` provides a bounded provider-independent local source:

- local RFC822 bytes/files only;
- no network activity;
- canonical `Message-ID` required;
- timezone-bearing `Date` required;
- explicit `In-Reply-To` / `References` threading only;
- optional native/provider message/thread IDs preserved when supplied;
- bounded `text/plain` body persistence;
- attachment bytes ignored;
- HTML-only input fails closed;
- no subject/name-similarity thread inference;
- persisted source `local-mailroom-rfc822`, scope `local_native`, authoritative `true`;
- local-native truth remains `production_provider_ready=false`.

`tools/mail_local_intake.py` is the operator intake entry point and constrains runtime persistence to `/var/lib/wwcx-mail-room`.

### Store and provenance

`server/mail_correspondence_store.py` persists immutable source, authority, and source scope. Supported scopes are `synthetic`, `local_native`, `production_native`, and fail-safe `legacy_unscoped`.

Only persisted records with `authoritative=true` and scope `local_native` or `production_native` can cross the Private AI correspondence-read boundary. Synthetic records cannot claim authority and cannot be upgraded by reopening the database. Read-only consumers use SQLite `mode=ro` and reject writes.

### Mail AI/API

`server/mail_ai_adapter.py` supports bounded message and thread reads. Correspondence reads remain disabled by default and fail closed unless the private store is valid and contains readable authoritative records.

`server/outbound_mail_gateway_server.py` exposes correspondence status/message/thread reads behind the existing HMAC/replay-protected loopback API. The endpoints additionally require exact client ID `wwcx-private-ai`.

A Phase 28 security review fixed potential privilege inheritance: the already-authorized `wwcx-website-admin` client does not inherit message-body access. `tests/validate_mail_correspondence_client_isolation.py` proves existing/unrelated HMAC clients are rejected from correspondence endpoints.

The 2026-08-19 approval now authorizes adding exact client ID `wwcx-private-ai` to the **deployed** Mail HMAC allowed-client policy and live-registering only the least-privileged Mail status/correspondence/draft BigBird capabilities. The existing secret mechanism must be reused without exposing, rotating, or committing secret values.

### BigBird repository integration

Merged components:

- `integrations/bigbird_mail/client.py`;
- `integrations/bigbird_mail/tools.py`;
- `integrations/bigbird-mail/tool-manifest.json`.

The client is loopback-only and HMAC-authenticated. The facade rechecks untrusted-content, non-mutation, no-send, and persisted provenance boundaries. It exposes repository tools for `mail.status.read`, `mail.correspondence.read`, and `mail.draft.prepare`; it has no send method. Draft preparation remains `prepared_not_sent`.

## MMS state

Phase 27's merged repository MMS implementation remains ready for live acceptance:

- private content-addressed quarantine store;
- SHA-256/integrity checks;
- fail-closed quarantine states;
- fixed `/usr/bin/clamscan` adapter;
- local clean/EICAR/error/restart acceptance tooling;
- no automatic quarantine release.

The 2026-08-19 approval explicitly covers installing/enabling the resource-safe local scanner/signature data if absent, creating the private MMS root under the actual service identity, restarting only directly affected services, and running synthetic live acceptance with rollback/evidence.

Live Edge1 scanner/private-root acceptance is still not claimed until an authenticated Edge1 execution connector is actually callable and the host tests pass. SMS/MMS `security_quarantine` therefore remains `degraded` for now.

## Existing shared runtime truth

Prior accepted live evidence remains unchanged unless later fresh Edge1 evidence proves otherwise:

- Messaging Gateway/PostgreSQL — runtime-ready from prior acceptance;
- BigBird — previously runtime-ready for accepted Messaging/communications/telephony scopes; Phase 28 Mail tools are merged but not yet live-accepted;
- Communications workspace/Relay — previously runtime-ready, loopback-only, authoritative Relay metadata attached;
- Voice/SIP — bounded read-only acceptance remains runtime-ready; current external interconnect health remains `unknown` because prior degraded display data came from a stored 2026-07-20 status snapshot rather than a fresh live probe.

## Remaining blocker

The previous authentication-policy approval blocker is **cleared**.

The remaining blocking condition for safe-scope completion is **callable authenticated Edge1 execution** so the approved deployment and live acceptance can actually run and produce evidence. The repository now contains a guarded Edge1 Live Shell MCP connector, but availability must be verified in the active operator session before any live claim.

A production-native Mail source is optional/separate from local safe-scope completion. Read-only discovery of an already-existing source is approved when it requires no new credentials/provider activation; provider-production readiness must not be claimed without actual native source evidence.

Exact live procedure: `docs/communications/unified-communications-phase28-live-acceptance-20260818.md`.

Approval record: `docs/communications/unified-communications-safe-scope-approval-20260819.md`.

`fresh_edge1_runtime_verified` remains false until live evidence passes.

## Still-protected production boundaries

The safe-scope approval does not authorize live SMS/MMS or email transmission, production calls, emergency/carrier routing changes, number porting, STIR/SHAKEN, credential disclosure/rotation, quarantine release, destructive/irreversible operations, provider financial/legal/regulatory commitments, or unrelated DNS/firewall/certificate/public-listener changes.
