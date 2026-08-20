# Mail Room durable engineering handoff — 2026-08-20

This is the current resume point for WW.CX Mail Room work. The 20260818 Mail Room handoff is historical only.

## Resume point

Use `main` at or after `942ab5b957ad89075ef27ff977b3c39e3ee8dca9` (PR #490).

Read first:

1. `.agent/mail-room-current-state-20260820.md`
2. `.agent/mail-room-backlog-20260820.md`
3. `docs/messaging/namecheap-private-email-imap-source-20260820.md`
4. `docs/communications/unified-communications-live-acceptance-20260819.md`
5. `docs/messaging-operations/mail-room-production-activation-checklist-20260818.md`

Then inspect current code/config/tests rather than trusting prose blindly.

## What is now verified

### Local Mail Room

The local correspondence path is not merely staged. It was live-accepted on Edge1 on 2026-08-19:

- `wwcx-outbound-mail-gateway.service` on loopback `127.0.0.1:8104`;
- private `/var/lib/wwcx-mail-room/correspondence.sqlite3` with mode `0600` and `wwcx-mail-gateway` ownership;
- authoritative `local_native` RFC822 records;
- Private AI status `ready_local_native`;
- authenticated message/thread reads;
- BigBird Mail reads and `prepared_not_sent` drafts;
- provider delivery/send remained disabled.

A fresh bounded Edge1 check on 2026-08-20 again found the Mail gateway service active/running and port 8104 listening. Current environment/drop-in values and DB row counts are not exposed by the bounded Operator tool, but the service did not simply disappear after acceptance.

### Provider state

Read-only Namecheap support evidence (ticket `NC-JDV-2953`, 2026-08-02) established:

- `ww.cx` Private Email Pro active through 2026-11-14;
- physical mailboxes `blank@ww.cx` and `domaincontact@ww.cx` active;
- no aliases;
- one unused mailbox slot;
- Catch-All -> `blank@ww.cx`;
- mailbox-level forwarding/filter rules remain unverified.

Fresh repository DNS inventory on 2026-08-20 at 22:53 UTC queried Cloudflare and Google resolvers. Both agreed:

- MX `10 mx1.privateemail.com`, `20 mx2.privateemail.com`;
- SPF `v=spf1 include:spf.privateemail.com ~all`;
- Dyn authoritative nameservers;
- no published DMARC record.

Therefore Namecheap Private Email remains the current public inbound provider for `ww.cx`. Google Workspace welcome/onboarding mail observed on 2026-08-16 still required domain verification and did not represent an MX cutover.

## Engineering completed in this continuation

### PR #488 — Namecheap provider-native read source

Merged as `5783f9d4c3a48e62af8a766bb8bac2c99dbedc0a`.

Adds a credential-injected, unregistered, read-only IMAP source pinned to `mail.privateemail.com:993` over verified TLS. It selects `INBOX` read-only, uses `BODY.PEEK[]`, reuses strict RFC822 normalization, persists authoritative `production_native` provenance, and implements no mailbox mutation or send path.

### PR #489 — provider-message isolation hardening

Merged as `9a0f1d51e3bd458c6ca1a6bee80d78f4f047de67`.

Adds numeric UID ordering and fail-closed per-message isolation so malformed/unsupported messages are held out and reported without weakening validation or blocking safe neighboring messages.

### PR #490 — provider inventory + fresh DNS evidence

Merged as `942ab5b957ad89075ef27ff977b3c39e3ee8dca9`.

Reconciles the Namecheap physical mailbox/Catch-All facts into `config/messaging/mail-provider-inventory.json`, records fresh resolver-consensus DNS evidence, and fixes the validator so refreshable evidence is checked structurally instead of hard-coding one obsolete workflow/artifact ID.

All exact-head relevant checks passed before merge, including repository-wide validation, Mail Room configuration consistency, DNS acceptance, Edge1 Operator Validation, and the read-only domain inventory capture.

## Important architectural distinction

Provider physical mailboxes are transport plumbing, not WW.CX public identities.

- Namecheap physical: `blank@ww.cx`, `domaincontact@ww.cx`.
- WW.CX logical internal delivery: `john-inbox@ww.cx`, `maildesk@ww.cx`.

Do not rename/provision provider objects just to force these names to match unless a later approved routing design requires it.

Catch-All to `blank@ww.cx` also means IMAP-fetched RFC822 `To`/`Cc` cannot always prove the SMTP envelope local-part. A live canary must inspect provider-added delivery headers before identity-sensitive automation claims exact original-recipient preservation.

## Remaining critical path

The missing engineering bridge is now implemented. The next step is a protected live-access decision, not another source-code prerequisite.

Smallest next action after explicit authorization:

1. choose the first physical mailbox for the canary;
2. use an approved secret location without disclosing the password;
3. run one bounded read-only IMAP canary with the merged Namecheap source;
4. inspect UIDVALIDITY/UID behavior and real provider delivery headers;
5. verify new records persist as authoritative `production_native` and are readable through the existing Mail Room boundary;
6. perform no send, mailbox mutation, provider configuration change, DNS change, or auto-reply activation.

Do **not** perform the live IMAP login merely because the code is merged. It requires the specific live credential/access authorization boundary to be crossed explicitly.

Other separately protected work remains: mailbox forwarding/filter inspection, production scanner integration, DNS/DMARC/signing changes, outbound delivery activation, live inbound cutover decisions, and quarantine release/deletion authority.

## Fen/Gus coordination

The WW.CX Fen/Gus Agent Room `02 Messages` folder is the active collaboration channel. Gus has posted live-state, provider-evidence, PR #488/#489 review, fresh DNS, and PR #490 updates there. Fen should reply there with any independent review findings rather than creating an unrelated communication trail.
