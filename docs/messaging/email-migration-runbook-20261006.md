# Email commissioning and domain migration runbook

## Current boundary

The Mail Room prepares drafts but does not send. Provider credentials, per-domain external DNS evidence and real delivery acceptance are pending. Five registered domains: ww.cx, creekco.ca, spiritcreekgardens.com, scgardens.ca and omegafx.com. No migration is implied by a local scanner canary.

Edge1 remains a private hidden authoritative primary. Publish validated mail records through the chosen public secondaries. Do not publish Edge1 in NS delegations or expose its DNS control plane. Preserve separate WireGuard private/public resolver paths and the AdGuard Home/Unbound recursive service. Coordinate record ownership, expected values, serials, TTLs and rollback with the DNS workstream before any edit.

## Preparation completed before DNS cutover

Readiness & health displays each domain's missing evidence, aggregate pending backlog, oldest pending age, storage capacity, service health, definition/rule updates, recovery result and access policy. Monitoring runs every five minutes; a report older than 15 minutes is stale. Pending mail older than 15 minutes, failed scans/services, low disk space and scanner archive-window overflow produce visible warnings. These are operator UI/report warnings; no external alert channel is implied.

The browser bridge verifies the existing portal session with the auth service and requires an admin role plus edge1.security.read. nginx still authenticates and overwrites trusted proxy context. Missing/expired sessions, spoofed role headers and non-admin roles are denied. Current admins share one operator workspace containing all registered mailboxes; private/company selectors are organizational views. Delegated readers/reviewers are not enabled. Before adding non-admin mailbox users, implement individual mailbox grants, separate drafts/preferences, thread-level filtering and actor audits. AVA uses a separate signed read interface and sees only released mail; explicit suggestions do not authorize sending, quarantine release or filter edits.

No automatic deletion is enabled. Decide retention for delivered mail, raw archives, drafts, quarantine, audit events and backups separately; do not activate deletion or impose invented legal periods during commissioning.

## Observed routing baseline

Run `tools/messaging/mail_dns_baseline.py` to capture current NS, SOA, MX, domain TXT and DMARC observations for all five domains. The private aggregate report and root-only backup record capture time. These use Edge1’s configured resolver and are observations, not proof of public authoritative propagation. DKIM selectors, desired routing and provider-owned aliases remain inputs from the DNS/provider commissioning workstream. Refresh and externally verify this baseline immediately before migration, because DNS work may change it.

## Per-domain evidence template

Record these fields in root-managed `/etc/wwcx/mail-commissioning.json`, under `domains.DOMAIN`: provider_credentials, public_dns, inbound_delivery, outbound_delivery, sender_authentication, rollback_rehearsal. Values should be concise states such as not_verified, pending, verified. Store detailed evidence in the private operations register, never credentials in this JSON. Recording verified does not enable delivery: readiness keeps sending disabled and migration uncommissioned until a separate deployment implements and validates activation.

Capture current authoritative/public NS and zone records, MX priorities/targets, SPF, DKIM selectors, DMARC policy/report destination, mail host A/AAAA, TTLs, existing provider route, mailbox/alias/catch-all ownership, desired outbound provider, expected envelope sender, TLS certificate path and rollback route. Avoid premature strict DMARC if existing authorized sending has not been inventoried. If direct sending is selected, provider port-25 availability, PTR and hostname/reputation acceptance must also be satisfied; do not assume direct SMTP is the chosen outbound design.

## Commission one domain at a time

1. Verify the mail snapshot/recovery report, capacity, admin access and scan/update health. Keep the current provider active. Record exact baseline DNS and mail routing.
2. Configure credentials privately and validate provider connectivity without fetching unrelated mail or sending real correspondence. Confirm inbox/alias mapping, original recipients and reply identity. Approve the intended intake mode: provider-native intake versus direct SMTP.
3. Prepare candidate DNS records jointly with DNS workstream. Check unique SPF record, authorized sources, correct DKIM selector/public key, DMARC alignment, MX targets and mail host addresses. Do not change NS delegation and mail routing in one unverified step.
4. Verify candidate public DNS from public authorities and at least two independent external resolvers. Private split-DNS results do not establish public propagation. Record expected versus observed answers and TTLs.
5. Enable the approved bounded test route and perform inbound/outbound/reply tests with designated test accounts. Confirm DKIM signature, SPF result where valid transport metadata exists, DMARC alignment, message threading and sender selection. Check normal mail, GTUBE/EICAR isolated probes, encrypted/oversize attachments, duplicate intake, scanner outage, quarantine review and phishing-report behavior. Test probes must not be sent to unsuspecting recipients.
6. Verify provider submission/delivery/bounce receipts, retry behavior, duplicate-send prevention and operator send approval. Prepared drafts are not sent. AVA must not obtain independent send or release authority.
7. Apply only approved MX/routing changes. Monitor new provider and old provider queues during DNS cache expiry; reconcile duplicate or late intake and preserve original Message-ID/recipient evidence.
8. Observe delivery and false-positive rates before tightening spam thresholds or DMARC policy. Keep the old provider accessible until late-arrival reconciliation and rollback checks are accepted.

## Rollback

Restore the captured DNS/routing values through the DNS candidate/apply workflow; account for resolver caches and TTLs. Stop new outbound submissions if identity/signing/routing is incorrect. Retain queued messages and audit evidence; do not purge quarantines or blindly resend. Reconcile already submitted messages against provider receipts before retrying. Provider mailbox access remains available during rollback. Restore mail data only through a separately authorized recovery procedure, with consistent SQLite backups and private Redis snapshot; never overwrite production with the rehearsal copy.

## Recovery and UI acceptance limits

`tools/messaging/mail_room_recovery_rehearsal.py` makes a root-only mail snapshot, restores copies to a disposable directory, checks SQLite integrity/table counts, verifies archive/config hashes, and loads the Redis snapshot into a temporary UNIX-socket-only Redis with no TCP listener. It never starts an SMTP gateway/AVA on restored data or restores production. This is a mail-layer rehearsal; booting a replacement server, off-host backup availability, recovery encryption keys and provider recovery remain part of the separate disaster-recovery workstream.

Automated API acceptance covers admin/non-admin/missing session checks, proxy/CSRF rejection, drafts and send-disabled behavior. UI structural/responsive checks supplement those tests. A signed-in desktop and phone visual walkthrough remains required if an authenticated browser is unavailable; do not label static checks as completed live visual acceptance.
