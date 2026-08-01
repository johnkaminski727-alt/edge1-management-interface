# WW.CX Multi-Domain Mail Hub

## Status

The repository defines a disabled, loopback-only routing and identity foundation. It does not create provider mailboxes, change MX records, alter DNS, install an Internet-facing SMTP listener, add forwarding rules, or enable production mail flow.

The inbound hub and outbound gateway share one identity registry for WW.CX, CreekCo, Spirit Creek Gardens, the short gardens domain, and OmegaFX.

## Canonical internal destinations

The former deployment placeholders have been replaced with concrete internal addresses:

- **`john-inbox@ww.cx`** — private delivery mailbox for every `john@...` identity;
- **`maildesk@ww.cx`** — separate shared delivery mailbox for company and role identities;
- **`noreply@ww.cx`** — outbound-only system identity, never an inbound destination.

`john-inbox@ww.cx` and `maildesk@ww.cx` are internal delivery targets. They are not advertised public identities and are not included as inbound aliases in the route table. `noreply@ww.cx` is also absent from inbound routing so it cannot become a reply sink by accident.

The addresses are now authoritative configuration names, but their actual mailbox accounts still need to be provisioned and access-controlled at the selected mail provider before routing is activated.

## Managed domains and routes

The disabled configuration manages:

- `ww.cx`;
- `creekco.ca`;
- `spiritcreekgardens.com`;
- `scgardens.ca`;
- `omegafx.com`.

There are 35 named routes:

- five private `john@...` routes deliver to `john-inbox@ww.cx`;
- thirty company and role routes deliver to `maildesk@ww.cx`.

Unknown recipients at a managed domain are quarantined. Recipients outside the managed domains are rejected. Catch-all delivery is not enabled.

## Private John stream

These addresses are private to John and converge only on `john-inbox@ww.cx`:

- `john@ww.cx`;
- `john@omegafx.com`;
- `john@creekco.ca`;
- `john@scgardens.ca`;
- `john@spiritcreekgardens.com`.

`john@spiritcreekgardens.com` remains John's primary personal work identity for Spirit Creek Gardens matters. Its inbound mail stays private even though the identity is used for work.

## Shared role stream

All non-`john@...` addresses converge on `maildesk@ww.cx`. This includes:

- WW.CX records, privacy, security, postmaster, and abuse;
- CreekCo contact, support, billing, sales, regulatory, complaints, porting, privacy, postmaster, and abuse;
- Spirit Creek Gardens contact, records, accounts, privacy, postmaster, and abuse;
- short gardens contact, records, postmaster, and abuse;
- OmegaFX contact, records, privacy, postmaster, and abuse.

The shared mailbox can later be delegated, ticketed, or connected to workflows without exposing the private John mailbox.

## Routing model

```text
Current hosted MX/provider
  -> authenticated provider webhook or trusted local-MTA adapter
  -> multi-domain inbound hub
       -> john@... recipient -> john-inbox@ww.cx
       -> named role recipient -> maildesk@ww.cx
       -> unknown managed recipient -> quarantine
       -> unmanaged domain -> reject
       -> minimal append-only audit event
```

The original recipient must remain available as metadata. The outbound gateway uses it to select the matching reply identity automatically.

## Identity-aware replies

The intended reply flow is:

1. preserve the original inbound recipient;
2. deliver the message to the correct private or shared internal mailbox;
3. pass the original recipient to the outbound gateway when replying;
4. replace any arbitrary submitted `From:` and `Reply-To:` values;
5. send from the identity that originally received the message;
6. use `noreply@ww.cx` only for explicitly system-generated messages.

Examples:

```text
Inbound to john@spiritcreekgardens.com
  -> deliver privately to john-inbox@ww.cx
  -> reply from john@spiritcreekgardens.com

Inbound to support@creekco.ca
  -> deliver to maildesk@ww.cx
  -> reply from support@creekco.ca
```

## API

```text
GET  /mail-hub/healthz
GET  /mail-hub/status
GET  /mail-hub/audit?limit=50
GET  /mail-hub/quarantine?limit=50
POST /mail-hub/ingest
```

The service binds only to loopback. A provider-specific adapter must authenticate the provider event before translating it into the normalized ingress contract.

The current contract does not accept or persist raw MIME content, message bodies, or attachment bytes. Audit records contain hashes and routing metadata only.

## Production gates

Before enabling inbound routing:

1. provision `john-inbox@ww.cx` as a John-only mailbox or protected delivery target;
2. provision `maildesk@ww.cx` as a separate shared mailbox or protected delivery target;
3. verify that neither internal address is exposed as a public catch-all;
4. configure access controls proving shared operators cannot read the private mailbox;
5. inventory every existing mailbox, alias, forwarder, list, and catch-all on all five domains;
6. select and authenticate an inbound provider adapter;
7. test all five private routes and all thirty shared routes;
8. verify original-recipient preservation, duplicates, loops, bounces, quarantine, and rollback;
9. obtain explicit authorization for each provider-routing or MX cutover.

The committed hub remains disabled and fails the production gates by design.

## Recommended pilot

Keep the current providers authoritative. Copy, journal, or forward one non-critical address into the authenticated hub, confirm delivery and original-recipient preservation, and only then expand the pilot. Do not make the hub the sole delivery dependency until both internal mailboxes and rollback procedures are proven.
