# Mail Room remaining blockers and backlog — 2026-08-20

See `.agent/mail-room-current-state-20260820.md` for the current verified state. The 20260818 Mail Room files remain historical only.

## Resolved

- Local-functional correspondence store and RFC822 intake exist, are tested, and were live-accepted on Edge1.
- Authenticated Private AI correspondence status/message/thread reads exist behind the dedicated `wwcx-private-ai` boundary.
- BigBird has bounded Mail status/read/prepared-draft tools; send and mutation authority remain absent.
- Fresh 2026-08-20 Edge1 checks confirm the outbound Mail gateway service is active/running and `127.0.0.1:8104` remains listening.
- The 2026-08-19 acceptance proved `/var/lib/wwcx-mail-room/correspondence.sqlite3` existed with private ownership/permissions and authoritative `local_native` records, and returned `ready_local_native`.
- `ww.cx` physical provider mailbox inventory is reconciled read-only from Namecheap support evidence: `blank@ww.cx`, `domaincontact@ww.cx`, no aliases, one unused slot, Catch-All to `blank@ww.cx`.
- Fresh Cloudflare + Google resolver consensus on 2026-08-20 confirms `ww.cx` still publishes Namecheap Private Email MX and SPF; Google Workspace onboarding did not replace the public MX path.
- Provider-native Namecheap IMAP source is implemented and merged (#488), hardened per message (#489), and deliberately unactivated.
- Canonical provider inventory and refreshable-evidence validation are updated and merged (#490).

## Remaining local visibility gap — narrowed, not blocking source engineering

The bounded Edge1 Operator connector cannot currently expose arbitrary systemd environment/drop-in contents or correspondence DB rows.

Therefore a fresh 2026-08-20 session has **not** independently re-read:

- the current value of `WWCX_MAIL_CORRESPONDENCE_READ_ENABLED`;
- the current row count/source mix in `/var/lib/wwcx-mail-room/correspondence.sqlite3`.

This no longer justifies saying the Mail Room is unproven or empty: the 2026-08-19 live acceptance already recorded `ready_local_native` with two authoritative records, and 2026-08-20 confirms the service/listener remain active.

Do not change the runtime solely to satisfy this observability gap. Re-inspect it opportunistically when an approved authenticated shell/operator surface can report the values without exposing secrets.

## Protected live provider activation — next critical path

### Namecheap read-only canary

**Implemented but not authorized for live execution:** `server/mail_namecheap_imap_source.py`.

Remaining steps require a separate live-access decision:

1. choose the first physical mailbox (`blank@ww.cx` is the Catch-All target, but selection is an activation decision);
2. identify an approved secret location without displaying or committing the mailbox credential;
3. explicitly authorize one bounded read-only IMAP login/canary;
4. fetch only a bounded tail over verified TLS using `BODY.PEEK[]`;
5. verify UIDVALIDITY/UID behavior, provider headers, duplicate handling, `production_native` provenance, and Mail Room readability;
6. keep the mailbox read-only and perform no SMTP/send action.

### Original-recipient evidence

Catch-All/Bcc semantics mean RFC822 `To`/`Cc` are not guaranteed to equal the SMTP envelope recipient.

The first live canary must determine whether Namecheap supplies a reliable `Delivered-To`, `X-Original-To`, or equivalent header. Until proven, identity-sensitive automation must fail closed rather than infer a recipient from incomplete evidence.

### Provider mailbox forwarding/filter rules

Namecheap support could not inspect mailbox-level Auto-forward or Filter rules. A logged-in webmail/provider review is still required if those rules matter to production routing. Do not change them without exact authorization.

## Other privileged / external blockers

### Mail scanner runtime

The local correspondence path is accepted, but final Mail inbound/outbound scanning still needs an approved production runtime and end-to-end proof at the secure submission/threat boundaries.

Do not weaken fail-closed scanning to make delivery easier.

### DNS/domain alignment

Fresh public DNS evidence now exists; no DNS mutation is authorized.

Current `ww.cx` facts:

- Namecheap Private Email MX present;
- Namecheap SPF present;
- no published DMARC record;
- provider support reported default DKIM configured on 2026-08-02, but actual production signing/alignment remains a separate verification item.

Any MX/SPF/DKIM/DMARC change requires exact authorization and rollback evidence.

### Live outbound provider activation

Still blocked on approved credentials, verified sender/alignment state, provider adapter activation, and separately authorized production transmission.

Automatic replies remain disabled during any initial provider testing.

### Quarantine operations

Durable release/deletion authority remains separately privileged. AI may not release quarantine or weaken hard security controls.

## Do not regress

- Do not treat physical `blank@ww.cx` or `domaincontact@ww.cx` as public sender identity merely because they are provider mailboxes.
- Do not expose `john-inbox@ww.cx` or `maildesk@ww.cx` as public send identities.
- Do not turn Catch-All proposals into live senders automatically.
- Do not guess original-recipient identity when provider evidence is ambiguous.
- Do not reintroduce heuristic ambiguous thread matching for automation.
- Do not allow scanner failure to become permissive.
- Do not let AI output/message content alter authorization or release quarantine.
- Do not enable provider transmission or auto-reply merely because repository CI is green.
- Do not put mailbox credentials in Git, Google Drive handoffs, logs, command arguments, or user-visible output.
