# WW.CX Multi-Domain Mail Hub

## Status

The repository defines a disabled, loopback-only routing and identity foundation. It does not create provider mailboxes, change MX records, alter DNS, install an Internet-facing SMTP listener, add forwarding rules, or enable production mail flow.

The inbound hub and outbound gateway share one identity registry for WW.CX, CreekCo, Spirit Creek Gardens, the short gardens domain, and OmegaFX.

## Canonical internal destinations

The former deployment placeholders have been replaced with concrete internal addresses:

- **`john-inbox@ww.cx`** — private delivery mailbox for every explicitly private `john@...` identity;
- **`maildesk@ww.cx`** — separate shared delivery mailbox for company/role identities and the managed-domain catch-all fallback;
- **`noreply@ww.cx`** — outbound-only system identity, never an inbound destination.

`john-inbox@ww.cx` and `maildesk@ww.cx` are internal delivery targets. They are not advertised public identities. `noreply@ww.cx` is absent from inbound routing so it cannot become a reply sink by accident.

The addresses are authoritative configuration names, but their actual mailbox accounts still need to be provisioned and access-controlled at the selected mail provider before routing is activated.

## Managed domains and routes

The disabled configuration manages:

- `ww.cx`;
- `creekco.ca`;
- `spiritcreekgardens.com`;
- `scgardens.ca`;
- `omegafx.com`.

There are 37 explicit route overrides:

- five private `john@...` routes deliver to `john-inbox@ww.cx`;
- thirty-two named company and role routes deliver to `maildesk@ww.cx`.

In addition, every local-part at a managed domain is accepted through the managed-domain catch-all fallback and delivered to `maildesk@ww.cx` unless an explicit route overrides it. Recipients outside the managed domains are rejected.

The exact original recipient remains preserved in the routing decision so the Mail Room can understand which address was used even when that address was not pre-registered.

## Private John stream

These explicitly registered addresses are private to John and converge only on `john-inbox@ww.cx`:

- `john@ww.cx`;
- `john@omegafx.com`;
- `john@creekco.ca`;
- `john@scgardens.ca`;
- `john@spiritcreekgardens.com`.

`john@spiritcreekgardens.com` remains John's primary personal work identity for Spirit Creek Gardens matters. Its inbound mail stays private even though the identity is used for work.

An arbitrary catch-all local-part that merely resembles a private address does not become private automatically. Private routing requires an explicit registered private identity so an attacker cannot manufacture a private-mailbox route by choosing a local-part.

## Shared Mail Room stream

All explicitly registered non-private role addresses converge on `maildesk@ww.cx`, and the managed-domain catch-all fallback also uses `maildesk@ww.cx`.

Named roles include:

- WW.CX records, privacy, security, postmaster, and abuse;
- CreekCo contact, support, billing, sales, regulatory, complaints, porting, accessibility, network operations, privacy, postmaster, and abuse;
- Spirit Creek Gardens contact, records, accounts, privacy, postmaster, and abuse;
- short gardens contact, records, postmaster, and abuse;
- OmegaFX contact, records, privacy, postmaster, and abuse.

The shared mailbox can later be delegated, ticketed, or connected to workflows without exposing the private John mailbox.

## Reconciled CreekCo identities

Round-trip tests performed on 2026-07-28 demonstrated inbound delivery and matching outbound reply identity for `accessibility@creekco.ca` and `noc@creekco.ca`. Those two operational identities are represented in both the inbound route table and the automatic sender-selection map:

- `accessibility@creekco.ca` — accessibility requests, accommodation correspondence, and accessible-service support;
- `noc@creekco.ca` — network operations, maintenance, carrier coordination, incidents, and technical escalation.

Both deliver internally to `maildesk@ww.cx`. Their sender profiles remain `outbound_enabled: false`; registering the identities does not authorize live gateway delivery.

## Routing model

```text
Current hosted MX/provider
  -> authenticated provider webhook or trusted local-MTA adapter
  -> multi-domain inbound hub
       -> explicit private identity -> john-inbox@ww.cx
       -> explicit role identity -> maildesk@ww.cx
       -> any other local-part at managed domain -> maildesk@ww.cx catch-all
       -> unmanaged domain -> reject
       -> minimal append-only audit event
```

The original recipient must remain available as metadata. The outbound gateway and Mail Room use it as the preferred reply identity candidate, subject to outbound authorization and provider verification.

## Identity-aware replies

The intended reply flow is:

1. preserve the exact original inbound recipient;
2. deliver the message to the correct private or shared internal mailbox;
3. pass the original recipient into reply identity resolution;
4. replace any arbitrary submitted `From:` and `Reply-To:` values;
5. prefer the identity that originally received the message when that identity is authorized for outbound use;
6. if a catch-all address is not yet an approved live sender, prepare the reply with that requested identity but block transmission until the sender is authorized or an approved fallback is explicitly selected;
7. use `noreply@ww.cx` only for explicitly system-generated messages.

Examples:

```text
Inbound to john@spiritcreekgardens.com
  -> deliver privately to john-inbox@ww.cx
  -> reply candidate john@spiritcreekgardens.com

Inbound to support@creekco.ca
  -> deliver to maildesk@ww.cx
  -> reply candidate support@creekco.ca

Inbound to new-project@creekco.ca
  -> catch-all delivery to maildesk@ww.cx
  -> preserve new-project@creekco.ca as the reply candidate
  -> send only if that identity is provider-verified/live-authorized
```

The system must not silently substitute a different legal entity or unrelated domain simply because the exact catch-all address is not yet authorized.

## Spam, phishing, malware, and catch-all safety

Catch-all delivery increases exposure to dictionary spam, random-recipient attacks, phishing, and malicious attachments. Production catch-all activation therefore requires the Mail Room threat pipeline described in `mail-room-threat-intelligence-and-ai-policy-20260818.md`.

The intended path combines sender authentication, reputation/blocklists, Rspamd scoring/phishing/fuzzy analysis, antivirus/YARA/content scanning, safe HTML handling, AI semantic threat classification, and quarantine.

Quarantine is preferred over silent deletion for suspicious accepted messages so false positives remain reviewable.

## API

```text
GET  /mail-hub/healthz
GET  /mail-hub/status
GET  /mail-hub/audit?limit=50
GET  /mail-hub/quarantine?limit=50
POST /mail-hub/ingest
```

The service binds only to loopback. A provider-specific adapter must authenticate the provider event before translating it into the normalized ingress contract.

The current contract still does not accept or persist raw MIME content, message bodies, or attachment bytes. Audit records contain hashes and routing metadata only. The later malware/phishing pipeline therefore requires a restricted provider/MTA staging layer with access to the actual message content before normal delivery.

## Production gates

Before enabling inbound routing:

1. provision `john-inbox@ww.cx` as a John-only mailbox or protected delivery target;
2. provision `maildesk@ww.cx` as a separate shared mailbox or protected delivery target;
3. verify that neither internal address is exposed as a public sender/catch-all identity;
4. configure access controls proving shared operators cannot read the private mailbox;
5. inventory every existing mailbox, alias, forwarder, list, and catch-all on all managed domains;
6. select and authenticate an inbound provider adapter;
7. prove explicit private overrides and managed-domain catch-all routing for every managed domain;
8. verify original-recipient preservation, duplicates, loops, bounces, quarantine, and rollback;
9. activate and validate the required spam/phishing/malware pipeline before making catch-all delivery authoritative;
10. obtain explicit authorization for each provider-routing or MX cutover.

The committed hub remains disabled and fails the production gates by design.

## Recommended pilot

Keep the current providers authoritative. Copy, journal, or forward one non-critical domain/address stream into the authenticated hub, confirm catch-all delivery, original-recipient preservation, threat filtering, and rollback, and only then expand the pilot. Do not make the hub the sole delivery dependency until both internal mailboxes and the security pipeline are proven.
