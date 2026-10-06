# Spirit Creek Gardens mail commissioning (2026-10-06)

Only john@ww.cx is private. Other addresses use the shared Mail Room.
Spirit Creek Gardens catch-all replies select the envelope recipient or contact@spiritcreekgardens.com. New messages in that domain default to contact.

Installed separate release directories scg-catchall-mailroom-20261006 and scg-catchall-gateway-20261006, preserving prior releases. Source includes the Mail Room features module captured from the running release; identity schema and sender UI changes are included here.
13 identity tests passed, JS syntax passed, candidate/live validation and Mail Room options passed. Services run with existing authentication, security scanning and outbound gates.
Local SMTP catch-all test ingested a BCC-only envelope recipient as an authoritative native message. Evidence /var/lib/wwcx-mail-gateway/scg-commissioning-test.json. Backups /var/backups/edge1-scg-mail-20261006.

PENDING: Dyn refused MX update over TSIG (REFUSED). No MX has been published; account UI sign-in is required to add @ MX priority 10 mail.ww.cx. TTL 600. Current website records remain unchanged.
Outgoing remains disabled until reverse DNS and live-pilot checks are completed. Last observed PTR vps-89-126-248-191.1984.is. PGP key creation has not been performed.
