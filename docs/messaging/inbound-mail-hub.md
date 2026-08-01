# WW.CX Multi-Domain Mail Hub

## Status

Implemented as a disabled, loopback-only routing and identity foundation. No MX record, mailbox rule, SMTP listener, firewall rule, reverse-proxy route, credential, provider setting, sender authorization, or production mail flow is changed by this branch.

The hub complements the outbound-mail compliance gateway. Together they form a provider-neutral correspondence control plane for WW.CX, CreekCo, Spirit Creek Gardens, the short gardens domain, and OmegaFX.

```text
Internet sender
  -> current or future MX/provider
  -> authenticated provider webhook or trusted local-MTA adapter
  -> WW.CX multi-domain inbound hub
       -> private John destination for every john@ address
       -> shared role destination for non-john company addresses
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

There are 35 named routes. They are deliberately divided into two delivery streams rather than converging into `john@ww.cx`:

- five private `john@...` routes use `CONFIGURE_PRIVATE_JOHN_MAILBOX`;
- thirty non-john company and role routes use `CONFIGURE_SHARED_ROLE_MAILBOX`.

These are deployment placeholders, not active mailbox addresses. They must be replaced with two different real destinations before production routing can be considered.

Unknown addresses at a managed domain are quarantined rather than silently discarded. Recipients outside managed domains are rejected. Catch-all delivery is intentionally not enabled because it increases spam load and can conceal address mistakes.

## Private John addresses

Every `john@...` address is intended only for John and belongs to the private mailbox stream:

- `john@ww.cx`;
- `john@omegafx.com`;
- `john@creekco.ca`;
- `john@scgardens.ca`;
- `john@spiritcreekgardens.com`.

`john@spiritcreekgardens.com` remains the primary personal work identity for Spirit Creek Gardens matters, but its inbound mail still belongs in John's private destination. It must not be used as the shared destination for role mail.

## Shared company and role addresses

Non-john addresses belong in the separate shared role stream. Examples include:

- `contact@creekco.ca`, `support@creekco.ca`, `regulatory@creekco.ca`, and `complaints@creekco.ca`;
- `records@spiritcreekgardens.com` and `accounts@spiritcreekgardens.com`;
- `contact@omegafx.com` and `records@omegafx.com`;
- `records@ww.cx`, `privacy@ww.cx`, and `security@ww.cx`;
- `privacy@...`, `postmaster@...`, and `abuse@...` where configured.

These addresses may later be shared with staff, delegated, ticketed, or connected to workflows without exposing John's private mailbox.

## Identity and reply behavior

The intended user experience is two inbox streams with identity-aware replies:

1. inbound mail retains the original recipient address;
2. every `john@...` recipient routes to John's private mailbox destination;
3. every non-john role recipient routes to the shared role mailbox destination;
4. replies default to the same identity that received the message;
5. Spirit Creek Gardens personal work replies default to `john@spiritcreekgardens.com`;
6. role addresses reply using their role identity when authorized;
7. shared users and workflows do not receive access to John's private mailbox;
8. outbound delivery remains blocked until SPF, DKIM, DMARC, provider authorization, and sender verification are complete.

The registry currently marks every outbound profile disabled. It describes intended identity behavior but does not authorize spoofing or sending from an unverified domain.

## Current routes

### Private John stream

`john@ww.cx`, `john@creekco.ca`, `john@spiritcreekgardens.com`, `john@scgardens.ca`, and `john@omegafx.com`.

### WW.CX shared roles

`records`, `privacy`, `security`, `postmaster`, and `abuse`.

### CreekCo shared roles

`contact`, `support`, `billing`, `sales`, `regulatory`, `complaints`, `porting`, `privacy`, `postmaster`, and `abuse`.

### Spirit Creek Gardens shared roles

`contact`, `records`, `accounts`, `privacy`, `postmaster`, and `abuse` at `spiritcreekgardens.com`.

### Short gardens shared roles

`contact`, `records`, `postmaster`, and `abuse` at `scgardens.ca`.

### OmegaFX shared roles

`contact`, `records`, `privacy`, `postmaster`, and `abuse` at `omegafx.com`.

## Why the first adapter is not a public SMTP listener

Running a direct MX requires a production MTA, public TCP 25 reachability, reverse DNS, TLS, queue management, spam and malware controls, abuse handling, bounce behavior, monitoring, patching, backup MX decisions, and a tested rollback. The current foundation therefore accepts normalized envelopes only from an authenticated provider webhook or a trusted local MTA on the private boundary.

This lets the organization centralize routing and audit behavior without turning the operations API into an Internet-facing mail server.

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
7. a real private John destination replacing `CONFIGURE_PRIVATE_JOHN_MAILBOX`;
8. a different real shared role destination replacing `CONFIGURE_SHARED_ROLE_MAILBOX`;
9. access controls proving the shared role destination does not expose John's private mail;
10. spam, malware, bounce, abuse, and queue procedures;
11. controlled tests to organization-owned mailboxes;
12. duplicate, loop, quarantine, and rollback verification;
13. explicit provider-routing or MX cutover authorization.

Outbound use of any sender identity separately requires provider sender verification, aligned envelope sender, SPF, DKIM, DMARC review, and explicit outbound activation.

The committed configuration fails all production gates by design.

## Recommended first production topology

```text
Existing hosted providers remain authoritative MX
  -> copied, journaled, forwarded, or webhook flow for selected addresses
  -> authenticated multi-domain hub
       -> private John mailbox for all john@ recipients
       -> separate shared role mailbox for all other named recipients
  -> identity-aware reply selection
```

Start with copied or journaled traffic where possible. That permits route verification without making the hub the sole delivery dependency.

## Cutover sequence

1. Inventory current MX records, providers, mailboxes, aliases, forwarders, mailing lists, and catch-all behavior for all five domains.
2. Select the private John mailbox destination.
3. Select a separate shared role mailbox destination and define who may access it.
4. Verify which listed addresses already exist and which must be created.
5. Keep all current providers authoritative while the hub remains disabled.
6. Deploy the loopback service and authenticated internal route.
7. Configure one provider webhook or local-MTA adapter with runtime secrets.
8. Replay synthetic envelopes for each domain and identity class.
9. Prove all five `john@...` addresses reach only the private destination.
10. Prove all thirty role addresses reach only the shared destination.
11. Pilot one non-critical copied or forwarded address per provider.
12. Verify delivery, original-recipient preservation, identity-aware replies, duplicates, loops, bounces, quarantine, access separation, and rollback.
13. Configure and verify outbound identities separately.
14. Authorize each provider-routing or MX change explicitly.

## Relationship to the outbound gateway

The inbound and outbound services should share the mail identity registry and one correspondence matrix keyed by WW.CX control ID, provider message-ID hashes, RFC Message-ID hashes, case ID, sender identity, recipients, delivery status, replies, and quarantine state. Message content should remain in the private mailbox, shared role mailbox, or an encrypted records store rather than the audit ledger.
