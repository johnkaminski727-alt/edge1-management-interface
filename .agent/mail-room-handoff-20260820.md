# Mail Room durable engineering handoff — 2026-08-20

Supersedes `.agent/mail-room-handoff-20260818.md` as the resume point. That file, and the rest of the `-20260818` mail-room set, describe the system only up to PR #369 and should not be read as current.

## Resume point

Use `main` at or after `c4a4b71de9393c1c47792e50e424c72488ce2be1`.

Read first:

1. `.agent/mail-room-current-state-20260820.md`
2. `.agent/mail-room-backlog-20260820.md`
3. `docs/messaging-operations/mail-room-production-activation-checklist-20260818.md` (still accurate — production activation posture has not changed)

Then inspect current code/config/tests rather than trusting any stale prose, including this file.

## Task that produced this handoff

John (direct chat instruction, 2026-08-20) asked Fen to take ownership of restoring the WW.CX Mail Room to a working state, working from live Edge1 evidence rather than old status docs, repairing anything safely repairable, and stopping before any privileged/external action.

## Finding

No code defect. The repository implementation is CI-green (`Validate repository`, `WW.CX Messaging Gateway`, `Edge1 Operator Validation` all `success` at HEAD) and every Mail Room test/validator passes except three that fail only under this session's Windows environment for confirmed non-repository reasons (NTFS `chmod`/permission-bit semantics and SQLite file-handle cleanup on Windows — see current-state file for detail).

What was actually stale was the `.agent` documentation: the 20260818 mail-room state/backlog/handoff files predate roughly 30 merged commits of real local-functional correspondence work (private SQLite store, local RFC822 intake, gated AI-adapter correspondence reads, authenticated correspondence API endpoints, BigBird tool integration) and gave a materially outdated picture of what exists.

## What was repaired this session

- Refreshed `.agent/mail-room-current-state-20260820.md` and `.agent/mail-room-backlog-20260820.md` against verified `git log`/CI/local-test evidence.
- This handoff file, updating the resume pointer.

No code, configuration, or runtime change was made. Nothing in `config/messaging/*.json` was touched — every `enabled`/`*_authorized`/`live_sender_allowlist` flag remains exactly as committed, which is correct: none of the privileged-blocker items changed.

## What remains open

1. **Live Edge1 visibility gap (not privileged, easy to close)**: this session had no Edge1 Operator MCP connector, so it could not confirm whether `wwcx-outbound-mail-gateway.service` is actually running on Edge1, whether `WWCX_MAIL_CORRESPONDENCE_READ_ENABLED` is set there, or whether any messages have been ingested into `/var/lib/wwcx-mail-room/correspondence.sqlite3`. A session with that connector should run `edge1.messaging_status` (read-only) and record the result. This is the single most useful next step and requires no new authorization.
2. **Privileged/external blockers** — unchanged from before this session: provider/mailbox reconciliation, scanner runtime selection, DNS/SPF/DKIM/DMARC, outbound provider credentials, live inbound cutover, quarantine operations. See `.agent/mail-room-backlog-20260820.md` for the smallest next action on each. None of these can or should be done by an autonomous session; each needs John's explicit authorization for the specific external action.

## Handoff to Gus/John

Fen → Gus/John: Mail Room repository state is verified healthy and CI-green at `c4a4b71d`; the "not usable" impression traced to stale `.agent` docs (now refreshed) plus the local-functional correspondence path being off-by-default and unverified-empty, not to any defect. The only thing blocking a fuller picture is that this session had no Edge1 Operator MCP connector — whoever picks this up next with that connector attached should run `edge1.messaging_status` and update `.agent/mail-room-current-state-20260820.md` with the live result. Everything requiring credentials, DNS, provider changes, or live send/receive remains exactly as gated as it was, per John's boundaries.
