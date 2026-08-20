# Mail Room verified repository state — 2026-08-20

## Why this file exists

`.agent/mail-room-current-state-20260818.md` (and its companion `-backlog-`/`-handoff-`/`-validation-` files from the same date) were never refreshed after Phase 27/28 landed. Reading only those files gives a false picture: they describe the system as of PR #369 (`50f5ef62`), but `main` has since merged roughly 30+ additional Mail Room commits. This file supersedes them for current-state purposes; the 20260818 files remain as historical record and should not be treated as authoritative for anything past `50f5ef62`.

## Authoritative checkpoint

Repository: `johnkaminski727-alt/edge1-management-interface`

Verified at inspection time: `main` = `c4a4b71de9393c1c47792e50e424c72488ce2be1` (PR #486, merged 2026-08-20T15:51Z). Working tree clean except an unrelated pre-existing case-collision artifact between `skills/wwcx-engineering-agent/SKILL.md` and `skill.md` on case-insensitive filesystems (not touched, not a Mail Room concern — worth a separate repo-hygiene fix at some point: two filenames differing only by case cannot both check out correctly on Windows/macOS).

CI at this commit is green: "Validate repository", "WW.CX Messaging Gateway", and "Edge1 Operator Validation" workflows all report `success`.

## What changed since the 20260818 checkpoint (PR #369 → HEAD)

A local-functional correspondence path was added on top of the PR #369 foundation:

- `server/mail_correspondence_store.py` — private SQLite correspondence store. Immutable per-record provenance (`source`, `source_authoritative`, `source_scope`); scope is one of `synthetic`, `local_native`, `production_native`, `legacy_unscoped`. Only `local_native`/`production_native` + `authoritative=true` records are readable by the AI adapter (`READABLE_AUTHORITATIVE_SCOPES`). File is created `0600`; a read-only open rejects any file with group/world bits set (`st_mode & 0o077`).
- `server/mail_local_rfc822_source.py` + `tools/mail_local_intake.py` — safe fallback native source. Parses local RFC822 bytes only (no network), requires a text/plain body, canonical `Message-ID`/`In-Reply-To`/`References`, and a timezone-bearing `Date`. Ingests as `source_scope=local_native`, `source_authoritative=true`. The intake CLI hard-constrains the target database to `/var/lib/wwcx-mail-room` (`ddfebe96 "Constrain local mail intake to private root"`) and always reports `send_authorized: false`, `mutation_authorized: false`, `network_activity: false`.
- `server/mail_ai_adapter.py` — bounded Private AI capabilities: `mail.status.read`, `mail.correspondence.read`, `mail.draft.prepare`. Correspondence reads are **disabled by default** and only become available when *all* of the following hold:
  1. `WWCX_MAIL_CORRESPONDENCE_READ_ENABLED=true` is set in the adapter's environment (default `false`);
  2. a database file exists at the configured path (default `/var/lib/wwcx-mail-room/correspondence.sqlite3`, overridable via `WWCX_MAIL_CORRESPONDENCE_DB` but still constrained under `/var/lib/wwcx-mail-room`);
  3. that database contains at least one record with an authoritative `local_native` or `production_native` source.
  Absent any of these, `correspondence_read_state()` reports `blocked_configuration_disabled`, `blocked_store_unavailable`, or `blocked_no_authoritative_records` rather than failing hard — this is fail-closed by design, not an error condition.
- `server/outbound_mail_gateway_server.py` / `server/outbound_mail_runtime_application.py` — the loopback HTTP admin API (port `8104`, `127.0.0.1`-only) now exposes authenticated correspondence-read endpoints (`/outbound-mail/api/v1/correspondence/status|message/{id}|thread/{id}`) gated to a single dedicated client id (`wwcx-private-ai`) distinct from the existing `wwcx-website-admin` HMAC client — the two client identities cannot borrow each other's authority (`validate_mail_correspondence_client_isolation.py`).
- `integrations/bigbird_mail/` — a loopback `MailGatewayClient` (HMAC-signed, hard-pinned to `http://127.0.0.1:8104`) plus BigBird tool wrappers. `integrations/bigbird-mail/tool-manifest.json` declares `mail.status.read`, `mail.correspondence.read`, `mail.draft.prepare` as the only tools, explicitly forbids `mail.send`, `mail.route.modify`, `generic.execute`, `quarantine.release`, and ships with **`default_enabled: false`** — BigBird does not get Mail Room tool access unless a separate BigBird-side config change turns it on.

None of this changes the production-activation posture below — it is entirely new *local, prepare-only, read-gated* capability layered on the existing fail-closed foundation.

## Why the mailbox looked "not usable" — verified finding

There is no code defect. Every Mail Room-focused test/validator in the repo passes (see Evidence). The perceived non-functionality has two independent, non-bug causes:

1. **Documentation drift** (fixed by this file): the `.agent` state files an operator or agent would read first were 2+ days stale and undersold what already exists — most importantly, that a working local correspondence read/draft path exists at all.
2. **Un-activated by design, on two separate axes**, neither of which is a defect:
   - *Production axis* (unchanged since PR #369): inbound routing, outbound provider delivery, live sender allow-list, and automatic replies are all still `enabled: false` / `*_authorized: false` in committed configuration. This requires the privileged external actions in `docs/messaging-operations/mail-room-production-activation-checklist-20260818.md` (provider inventory, DNS/SPF/DKIM/DMARC, scanner runtime, credentials) — none of which this session can or should perform.
   - *Local-functional axis* (new): even the read-only local correspondence path ships **off** by default (`WWCX_MAIL_CORRESPONDENCE_READ_ENABLED` unset) and **empty** (no RFC822 message has been ingested via `tools/mail_local_intake.py` into `/var/lib/wwcx-mail-room/correspondence.sqlite3` as far as this session can verify — see Blocked verification below). Turning this on is a bounded, reversible, non-production operator action (env var + running the intake CLI against real local mail files), not a code change — but it still requires action on the actual Edge1 host, which this session cannot reach.

## Blocked verification — no live Edge1 host access in this session

This session (Claude Code / "Fen") has git/GitHub access to this repository but **no connection to the Edge1 Operator MCP surface** (`edge1.health`, `edge1.messaging_status`, `edge1.services`, etc. — see `docs/edge1-operator/tool-contract.md`) that Gus/ChatGPT normally uses to inspect the live host. Everything above was verified against the repository (source, config, CI results, `git log`) and against local execution of the mail test suite; nothing above is a claim about the live Edge1 host's actual running state, because this session has no channel to observe it.

Concretely blocked without that access:
- Whether `wwcx-outbound-mail-gateway.service` (`deploy/messaging/wwcx-outbound-mail-gateway.service`) is installed and running on Edge1.
- Whether `WWCX_MAIL_CORRESPONDENCE_READ_ENABLED` is set in that service's environment.
- Whether `/var/lib/wwcx-mail-room/correspondence.sqlite3` exists on Edge1 and whether any messages have been ingested into it.
- General host/service health, logs, and listener state.

**Smallest concrete next action**: have an agent/session with Edge1 Operator MCP access (Gus, or a Fen session with that connector attached) run `edge1.messaging_status` (and `edge1.services` if needed) and report back the outbound-mail-gateway service state, whether the correspondence env var is set, and whether the correspondence DB/file exists. That single read-only call resolves the remaining uncertainty in this file without any privileged or irreversible action.

## Evidence (this session, 2026-08-20)

- `git log --oneline -25` on `main`, `git log 50f5ef62..HEAD --stat` for mail-touching paths — confirms 30+ merged Mail Room commits after the 20260818 checkpoint.
- `gh run list --branch main --json ...` — "Validate repository", "WW.CX Messaging Gateway", "Edge1 Operator Validation" all `success` at `c4a4b71d`.
- Local run of `tests/validate_outbound_mail_gateway.py` (52 tests OK), `tests/validate_mail_ai_adapter.py`, `tests/validate_mail_correspondence_client_isolation.py`, `tests/test_mail_threading.py`, `tests/test_mail_quarantine.py`, `tests/test_mail_threat_decision.py`, `tests/test_mail_config_consistency.py`, `tests/test_outbound_mail_admin_assets.py` — all pass.
- `tests/validate_mail_correspondence_store.py`, `tests/validate_mail_correspondence_functional.py`, and `tests/validate_outbound_mail_runtime_correspondence.py` fail *in this Windows session only*: SQLite file-handle cleanup and POSIX `chmod`/permission-bit checks behave differently on NTFS/Windows than on the Linux hosts CI and Edge1 run on (e.g. `path.chmod(0o644)` does not reliably clear group/world bits on Windows, tripping the store's `st_mode & 0o077` guard; SQLite keeps a Windows file handle open past `TemporaryDirectory` cleanup). These are confirmed environment artifacts, not repository defects — the same tests are part of the green "WW.CX Messaging Gateway" CI run on Linux at this commit.
