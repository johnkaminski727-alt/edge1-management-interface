# Mail Room commissioning corrections — 2026-10-07

Receiving catch-all mail uses the explicit `catch_all_domains` registry, independently
of the outbound sender allowlist. Malware, attachment, phishing, spam and incomplete
inspection findings still apply. The exact operator Outlook identity is exempt from
the protected-name heuristic only when independently checked DKIM and DMARC pass;
its address is stored in `/etc/wwcx/mail-security-policy.json` under
`authenticated_external_identities`.

Matching multi-recipient deliveries share one correspondence record with all observed
envelope recipients. Raw per-recipient files remain separate. All non-transit headers
and complete MIME content must match before merging; changed bodies or attachments
remain held. Secondary delivery metadata points to the canonical security inspection.

HTML-only bodies produce inert plain text. Invalid live Date headers use the recorded
local archive receipt timestamp, explicitly identified in normalization metadata.
Original RFC822 files are never rewritten.

Legacy PrivateEmail repairs use read-only IMAP INTERNALDATE with UIDVALIDITY checking.
Unusable message IDs receive archive-hash-bound internal IDs. Invalid recipient headers
fall back to the physical source mailbox, with the adjustment recorded. Invalid thread
headers stay in the original rather than becoming invented relationships. Security
inspections always read the untouched original, including every attachment.

Tools:
- `privateemail_repair_history.py`: recover legacy projections; preserve originals.
- `privateemail_security_backfill.py`: bounded parallel inspections through the ordinary security engine.
- `mail_room_quarantine_reconcile.py`: correct only completed policy-only false positives; preserve operator overrides and hard holds.

Validation: 17 security/commissioning regression tests and archive-first acceptance.
Deployment: immutable intake/security release copies, a scanner unit override and
Postfix's archive pipe path. Backups and closure evidence remain private on Edge1.
External production DNS rollback was not performed. Historical files that fail the
whole-message scan remain preserved in import holds and are not force-released.

## Follow-up acceptance — 2026-10-08

Seven individually reviewed Namecheap order/setup messages were released through the
existing fingerprint-bound operator-review action. Sender-wide trust was not changed.

Ten previous import holds are now visible in Quarantine with safely extracted text.
The original attachment bytes remain blocked: six encrypted PDFs, one encrypted ZIP,
and three ClamAV scan-size-limit findings. These findings are not a claim of confirmed
infection. Metadata records `import_security_hold` so a later clean scan cannot bypass
attachment review. Raw archives and provider originals remain unchanged.

`privateemail_visible_scan_holds.py` projects these reviewed scan holds;
`privateemail_repair_history.py --receipt-metadata-only` fetches only their provider
receipt dates under read-only IMAP selection and UIDVALIDITY verification.

Validation: 18 regression tests plus archive-first acceptance. All copied historical
messages are accounted for as imported, visible quarantine, duplicate or preserved
original-provider-folder archives. Live public DNS rollback remains unperformed;
the existing isolated transaction rehearsal does not establish provider permissions.

## DNS rollback rehearsal — 2026-10-08

`tools/messaging/mail_dns_rollback_rehearsal.py` validated disposable historical
MX rollback candidates and exact return to Edge1 for all five domains with
`named-checkzone`. An unrelated TXT record survived each change. Live MX was
queried before and after and stayed `10 mail.ww.cx.` for every domain.
This is an isolated MX-record rehearsal, not a complete zone restoration or
provider mutation-permission test. No public records changed and no mail was sent.

Production rollback remains unverified. SCG's historical baseline has no MX and
is not a usable fallback. OmegaFX's historical cPanel MX conflicts with the later
PrivateEmail account history. Verify provider routing, fallback recipient/catch-all
coverage and write permissions before using either as an emergency destination.
The existing per-domain rollback gates remain `not_verified`.
