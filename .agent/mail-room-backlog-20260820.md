# Mail Room remaining blockers and backlog — 2026-08-20

Supersedes `.agent/mail-room-backlog-20260818.md` for current-state purposes; that file is kept as history. See `.agent/mail-room-current-state-20260820.md` for the full verified state this backlog is based on.

## Resolved since 20260818

- A unified local-functional correspondence read path now exists (`server/mail_correspondence_store.py`, `server/mail_local_rfc822_source.py`, `tools/mail_local_intake.py`, `server/mail_ai_adapter.py` correspondence reads, authenticated correspondence endpoints on the loopback gateway API, client-isolated from the existing website-admin client). This was the "exact next engineering action" the 20260818 handoff called out as highest-value; it is done, tested, and CI-green.
- BigBird has a bounded, read/prepare-only mail tool surface (`integrations/bigbird_mail/`), explicitly forbidding send/route-modify/execute/quarantine-release, and disabled by default pending a separate BigBird-side enable decision.

## New: visibility blocker (not privileged, but currently unresolved)

Blocked: confirming live Edge1 host state for the outbound-mail-gateway service and the local correspondence store (installed/running status, `WWCX_MAIL_CORRESPONDENCE_READ_ENABLED` value, whether `/var/lib/wwcx-mail-room/correspondence.sqlite3` exists and has been populated).

Requires: a session with Edge1 Operator MCP access (this Fen session did not have one attached).

Smallest next action: run `edge1.messaging_status` (read-only) from a session that has the Edge1 Operator connector and report the outbound-mail-gateway service state back into this file or a new dated one.

This is not a privileged/external blocker in the sense of the items below — it needs no new authorization, only a session with the existing read-only connector attached.

## Privileged / external blockers (unchanged from 20260818 — still not performed autonomously)

### Provider and mailbox reconciliation

Blocked: verify/export actual provider-side mailbox, alias, forwarding, and sender-verification state for every managed domain; provision anything missing.

Requires: provider account access and potentially external production state changes.

Smallest future operator action: obtain a read-only provider inventory/export first. If changes are then needed, authorize the exact provisioning action separately.

### Final scanner runtime

Blocked: connect an approved server-side scanner adapter to the final outbound scan boundary and inbound threat pipeline.

Requires: runtime/service selection and configuration; engine installation/operation may affect production services.

Smallest future operator action: select/approve the runtime scanner and authorize installation/configuration on the intended host.

### Production DNS and domain alignment

Blocked: MX/SPF/DKIM/DMARC changes, domain verification/alignment, and live acceptance routing.

Requires: DNS/provider privileges and production traffic decisions.

### Live outbound provider activation

Blocked: credentials, sender verification, provider adapter activation, and production test transmission.

Requires: provider credentials and explicit authorization for production email transmission.

### Live inbound cutover

Blocked: production webhook/local-MTA/provider routing, mailbox delivery, and real-message acceptance tests.

Requires: provider/routing credentials and explicit live inbound authorization.

### Quarantine operations

Blocked: durable quarantine storage/runtime integration, privileged release execution, and destructive retention/deletion policy.

Requires: operational/security policy and explicit authorization for any release/deletion with external consequences.

## Do not regress (unchanged, still true at HEAD)

- Do not turn catch-all proposals into live senders automatically.
- Do not expose `john-inbox@ww.cx` or `maildesk@ww.cx` as public send identities.
- Do not reintroduce heuristic ambiguous thread matching for automation.
- Do not allow scanner error/unavailability to become permissive.
- Do not allow AI output or message content to change authorization, weaken hard risk, or release quarantine.
- Do not enable auto-reply or provider transmission merely because repository CI is green.
- Do not enable `WWCX_MAIL_CORRESPONDENCE_READ_ENABLED` or the BigBird mail integration's `default_enabled` flag as a side effect of unrelated work — each is a deliberate, separately-owned activation decision.
