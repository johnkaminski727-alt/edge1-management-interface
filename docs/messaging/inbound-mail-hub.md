# WW.CX Multi-Domain Mail Hub

## Status

Implemented as a disabled, loopback-only routing and identity foundation. No MX record, mailbox rule, SMTP listener, firewall rule, reverse-proxy route, credential, provider setting, sender authorization, or production mail flow is changed by this branch.

The hub complements the outbound-mail compliance gateway. Together they form a provider-neutral correspondence control plane for WW.CX, CreekCo, Spirit Creek Gardens, the short gardens domain, and OmegaFX.

```text
Internet sender
  -> current or future MX/provider
  -> authenticated provider webhook or trusted local-MTA adapter
  -> WW.CX multi-domain inbound hub
       -> explicit recipient route
       -> quarantine for unknown managed-domain recipients
       -> reject unmanaged domains
       -> minimal append-only audit event

WW.CX admin / workflow
  -> identity-selected outbound compliance gateway
  -> approved provider
  -> recipient
```

## Managed domains

The disabled configuration contains five managed domains:

- `ww.cx`;
- `creekco.ca`;
- `spiritcreekgardens.com`;
- `scgardens.ca`;
- `omegafx.com`.

There are 35 named routes. Every route currently delivers to the existing `john@ww.cx` mailbox during the pilot. This provides separate public identities without forcing separate inboxes immediately.

Unknown addresses at a managed domain are quarantined rather than silently discarded. Recipients outside managed domains are rejected. Catch-all delivery is intentionally not enabled because it increases spam load and can conceal address mistakes.

## Personal and work identity model

The shared identity registry classifies these as personal John aliases:

- `john@ww.cx`;
- `john@omegafx.com`;
- `john@creekco.ca`;
- `john@scgardens.ca`.

The primary Spirit Creek Gardens work identity is:

- `john@spiritcreekgardens.com`.

That address should be used for Spirit Creek Gardens corporate, gardens, accounting, privacy, claims, records, vendor, banking, insurance, and government correspondence issued personally by John.

Role addresses remain separate from personal aliases. Examples include:

- `contact@creekco.ca`, `support@creekco.ca`, `regulatory@creekco.ca`, and `complaints@creekco.ca` for telecommunications matters;
- `records@spiritcreekgardens.com` and `accounts@spiritcreekgardens.com` for company records and financial correspondence;
- `contact@omegafx.com` and `records@omegafx.com` for OmegaFX business matters;
- `privacy@...`, `postmaster@...`, and `abuse@...` where configured.

The short `scgardens.ca` domain is treated as a legacy or compatibility identity. Its `john@` address is personal, but the domain is not the preferred outbound work identity.

## Reply and sender behavior

The intended user experience is one inbox with identity-aware replies:

1. inbound mail retains the original recipient address;
2. the hub assigns the matching identity profile;
3. replies default to the same domain and role that received the message;
4. a personal alias replies as John;
5. Spirit Creek Gardens work correspondence defaults to `john@spiritcreekgardens.com`;
6. role addresses reply using their role identity when authorized;
7. outbound delivery remains blocked until SPF, DKIM, DMARC, provider authorization, and sender verification are complete.

The registry currently marks every outbound profile disabled. It describes intended identity behavior but does not authorize spoofing or sending from an unverified domain.

## Why the first adapter is not a public SMTP listener

Running a direct MX requires a production MTA, public TCP 25 reachability, reverse DNS, TLS, queue management, spam and malware controls, abuse handling, bounce behavior, monitoring, patching, backup MX decisions, and a tested rollback. The current foundation therefore accepts normalized envelopes only from an authenticated provider webhook or a trusted local MTA on the private boundary.

This lets the organization centralize routing and audit behavior without turning the operations API into an Internet-facing mail server.

## Current routes

### WW.CX

`john`, `records`, `privacy`, `security`, `postmaster`, and `abuse`.

### CreekCo

`john`, `contact`, `support`, `billing`, `sales`, `regulatory`, `complaints`, `porting`, `privacy`, `postmaster`, and `abuse`.

### Spirit Creek Gardens

`john`, `contact`, `records`, `accounts`, `privacy`, `postmaster`, and `abuse` at `spiritcreekgardens.com`.

### Short gardens domain

`john`, `contact`, `records`, `postmaster`, and `abuse` at `scgardens.ca`.

### OmegaFX

`john`, `contact`, `records`, `privacy`, `postmaster`, and `abuse` at `omegafx.com`.

## API

```text
GET  /mail-hub/healthz
GET  /mail-hub/status
GET  /mail-hub/audit?limit=50
GET  /mail-hub/quarantine?limit=50
POST /mail-hub/ingest
```

The service binds only to loopback. Production access must be provided through an authenticated internal reverse proxy or a local MTA adapter.

`POST /mail-hub/ingest` expects a normalized JSON envelope and the `X-WWCX-Inbound-Token` header. A provider-specific adapter should verify the provider's native signature first, then translate the event into this contract.

```json
{
  "envelope_from": "sender@example.com",
  "recipients": ["john@spiritcreekgardens.com"],
  "message_size": 4096,
  "provider_message_id": "provider-specific-id",
  "subject": "Example subject"
}
```

The current contract deliberately does not accept raw MIME content. That prevents accidental message-body or attachment persistence before encrypted content storage, malware scanning, retention, access control, and privacy procedures are selected.

## Data minimization

Audit records include event time, hashes of the provider message ID, envelope sender and subject, message size, recipient count, and routing decisions.

They do not include raw provider message IDs, message bodies, attachment bytes, raw MIME content, or authentication tokens.

Quarantine records contain routing metadata only. A later content quarantine needs encrypted storage, malware scanning, access control, retention, deletion, and export procedures.

## Activation gates

Production routing requires:

1. hub enablement;
2. deployment and production-routing authorization;
3. an enabled ingress profile and runtime secret;
4. authenticated operations routing;
5. a selected MX or inbound provider;
6. verified mailbox, alias, and forwarding inventory for all five domains;
7. spam, malware, bounce, abuse, and queue procedures;
8. controlled tests to organization-owned mailboxes;
9. duplicate, loop, quarantine, and rollback verification;
10. explicit provider-routing or MX cutover authorization.

Outbound use of any sender identity separately requires provider sender verification, aligned envelope sender, SPF, DKIM, DMARC review, and explicit outbound activation.

The committed configuration fails all production gates by design.

## Recommended first production topology

```text
Existing hosted providers remain authoritative MX
  -> copied, journaled, forwarded, or webhook flow for selected addresses
  -> authenticated multi-domain hub
  -> john@ww.cx central delivery mailbox
  -> identity-aware reply selection
```

Start with copied or journaled traffic where possible. That permits route verification without making the hub the sole delivery dependency.

## Cutover sequence

1. Inventory current MX records, providers, mailboxes, aliases, forwarders, mailing lists, and catch-all behavior for all five domains.
2. Verify which listed addresses already exist and which must be created.
3. Keep all current providers authoritative while the hub remains disabled.
4. Deploy the loopback service and authenticated internal route.
5. Configure one provider webhook or local-MTA adapter with runtime secrets.
6. Replay synthetic envelopes for each domain and identity class.
7. Pilot one non-critical copied or forwarded address per provider.
8. Verify delivery, original-recipient preservation, identity-aware replies, duplicates, loops, bounces, quarantine, and rollback.
9. Configure and verify outbound identities separately.
10. Authorize each provider-routing or MX change explicitly.

## Relationship to the outbound gateway

The inbound and outbound services should share the mail identity registry and one correspondence matrix keyed by WW.CX control ID, provider message-ID hashes, RFC Message-ID hashes, case ID, sender identity, recipients, delivery status, replies, and quarantine state. Message content should remain in the authoritative mailbox or an encrypted records store rather than the audit ledger.
