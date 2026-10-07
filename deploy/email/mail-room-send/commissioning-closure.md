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
