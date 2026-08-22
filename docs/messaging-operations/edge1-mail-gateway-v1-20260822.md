# Edge1 Mail Gateway v1

Date: 2026-08-22
Status: design/preparation only; production activation disabled

## Objective

Build a provider-neutral inbound mail gateway on Edge1 with the stable public service identity `mail.ww.cx`. Selected domains can later move their MX to this gateway one at a time, while `ww.cx` remains on its existing Namecheap Private Email path until a separate migration decision is made.

The gateway is an intake boundary for Mail Room and Cookie Monster. It is not an authorization to enable production MX changes, outbound delivery, persistent polling, or public listener changes.

## Durable decisions

1. `mail.ww.cx` is the service identity. Do not label it as a test host.
2. `ww.cx` stays on Namecheap Private Email for the initial gateway rollout.
3. The existing `blank@ww.cx` Namecheap IMAP connector remains the proven fallback/bridge path for Mail Room.
4. `domaincontact@ww.cx` remains a distinct administrative/domain-authority identity and must not be collapsed into generic catch-all traffic.
5. Initial Edge1 MX migration candidates are `creekco.ca`, `spiritcreekgardens.com`, `scgardens.ca`, and `omegafx.com`.
6. Domains migrate individually, never as a batch.
7. Catch-all behavior is implemented at the Edge1 virtual-domain layer and must preserve the exact original recipient.
8. Mail Room storage remains provider-neutral and authoritative provenance must identify the source transport.
9. Existing Namecheap/cPanel adapters remain available as migration/rollback tools; do not delete them when a domain moves.
10. DNS, certificates, firewall, production SMTP listeners, and provider cancellation remain separate approval boundaries.

## Target topology

```text
Internet
   |
   | domain MX
   v
mail.ww.cx
   |
   v
Edge1 inbound SMTP gateway (Postfix or equivalent)
   |
   +--> virtual-domain routing / catch-all
   |
   +--> per-domain durable Maildir/raw RFC822 storage
   |
   +--> threat/spam decision pipeline
   |
   v
Mail Room correspondence normalization
   |
   +--> production_native provenance
   |
   +--> Cookie Monster ingestion/read models
```

## Domain migration plan

### ww.cx

Initial state: **stay external**.

- Provider: Namecheap Private Email.
- Current public MX: `mx1.privateemail.com` / `mx2.privateemail.com`.
- `blank@ww.cx`: existing catch-all target and proven Mail Room IMAP ingestion source.
- `domaincontact@ww.cx`: administrative/domain-authority identity.

No `ww.cx` MX change is part of v1 rollout.

### creekco.ca

Target:

```text
*@creekco.ca -> Edge1 virtual-domain catch-all -> archive storage -> Mail Room
```

Preferred intake identity: `archive@creekco.ca` as the logical catch-all archive destination, while exact original recipients remain preserved as metadata/provenance.

Existing role identities in `mail-identities.json` remain valid and do not need separate physical mailboxes merely to receive mail.

### spiritcreekgardens.com

Target:

```text
*@spiritcreekgardens.com -> Edge1 virtual-domain catch-all -> archive storage -> Mail Room
```

The 2026-08-20 inventory observed no published MX. This makes the domain a good candidate after the gateway is proven, but DNS must not be changed until the complete acceptance gate passes.

### scgardens.ca

Target is the same virtual-domain catch-all model. Treat `scgardens.ca` as a separate domain from `spiritcreekgardens.com`; do not silently alias or merge their identity/provenance.

### omegafx.com

Target:

```text
*@omegafx.com -> Edge1 virtual-domain catch-all -> archive storage -> Mail Room
```

The previous provider mailbox assumptions around `webmaster@omegafx.com` are not part of the target architecture. Existing provider credentials may remain as rollback/migration evidence until Edge1 migration acceptance is complete.

## Mail storage model

Use domain isolation underneath a dedicated Edge1 mail root. Exact implementation may be Maildir or another append-safe RFC822 store, but each domain must have an independent boundary.

Example:

```text
/var/lib/wwcx-mail-gateway/
  domains/
    creekco.ca/
      archive/
    spiritcreekgardens.com/
      archive/
    scgardens.ca/
      archive/
    omegafx.com/
      archive/
  quarantine/
  evidence/
  state/
```

Requirements:

- service-owned; not world-readable;
- per-domain separation;
- durable raw RFC822 bytes until normalized/retention policy allows removal;
- original envelope recipient retained independently from visible `To`/`Cc`;
- messages are untrusted content and confer no authorization;
- backups and rollback are documented before migration.

## SMTP/MTA layer

Evaluate Postfix as the initial Edge1 MTA because Postfix is already present on Edge1. The v1 configuration should use virtual domains/aliases rather than local Unix users for each address.

Required controls before public activation:

- explicit managed-domain allowlist;
- reject relay for unmanaged domains;
- catch-all mapping scoped only to approved managed domains;
- exact envelope recipient preservation;
- size limits and connection/rate limits;
- TLS with an approved certificate deployment path;
- threat/spam handling with fail-closed policy where required;
- logs that do not expose message bodies or credentials;
- no outbound relay capability unless separately authorized.

## IMAP/Dovecot decision

Dovecot is optional for v1.

Mail Room itself does not require IMAP if the local MTA can deliver raw RFC822/Maildir messages directly into the ingestion boundary. Prefer the simpler direct local source when practical.

Add Dovecot only if humans or other authenticated clients need mailbox access. Do not install or expose it merely because the prior provider architecture used IMAP.

## Mail Room ingestion contract

The local Edge1 source must normalize into the same provider-neutral correspondence model already used by Namecheap ingestion.

At minimum preserve:

- envelope sender;
- exact envelope/original recipient;
- `Delivered-To`/`X-Original-To` equivalents where generated;
- Message-ID;
- In-Reply-To;
- References;
- received timestamp;
- raw RFC822 digest;
- attachment metadata/digests as policy allows;
- domain;
- transport provenance.

Target provenance example:

```json
{
  "authoritative": true,
  "scope": "production_native",
  "source": "edge1-mail-gateway-smtp"
}
```

## Catch-all semantics

Catch-all must not imply outbound authority.

Receiving `anything@creekco.ca` does not grant permission to send as that address. Outbound identities continue to be governed by `mail-identities.json`, outbound policy, sender allowlists, and explicit activation gates.

## Credential strategy

The Edge1 SMTP gateway should eliminate external IMAP credential requirements for migrated domains.

Existing provider credentials stay under `/etc/wwcx/credentials/` only while needed for migration, rollback, or historical provider access.

Do not place secrets in Git, evidence files, agent state, or Mail Room records.

## DNS and service identity

`mail.ww.cx` is the intended stable hostname for the gateway.

Before any domain MX change:

1. `mail.ww.cx` forward DNS resolves to the intended Edge1 public address.
2. reverse DNS strategy is documented; required mainly for outbound reputation but still useful operationally.
3. TLS certificate path is validated.
4. TCP/25 reachability is validated through an explicitly authorized firewall/listener change.
5. SMTP banner/hostname alignment is validated.
6. test delivery to a non-production or specifically authorized recipient path succeeds.

No DNS/firewall/certificate changes are authorized by this document.

## SPF, DKIM, DMARC

Inbound-only migration does not require Edge1 to originate mail for the migrated domain.

Do not change SPF/DKIM/DMARC merely to move inbound MX unless a record is directly required for the chosen provider/transport behavior.

If outbound mail later originates from Edge1, that is a separate activation project requiring:

- SPF alignment;
- DKIM signing;
- DMARC policy review;
- PTR/rDNS and reputation review;
- bounce/complaint handling;
- explicit live-send authorization.

## Migration acceptance gate

A domain may move MX only after all items below pass:

### Repository

- disabled-by-default gateway configuration validates;
- managed-domain and catch-all mappings validate;
- Mail Room local-source normalization tests pass;
- relay-denial tests pass;
- duplicate-ingestion/idempotency tests pass;
- threat-policy tests pass.

### Live Edge1

- gateway service installed but not publicly exposed until approved;
- storage ownership/modes verified;
- listener scope verified;
- local SMTP injection produces exactly one Mail Room record;
- exact original recipient survives normalization;
- backup/rollback verified;
- logs/evidence sanitized.

### DNS migration

- capture old MX/SPF/DKIM/DMARC/NS values;
- establish rollback record set;
- lower TTL only if explicitly approved and useful;
- change one domain only;
- wait for resolver consensus;
- perform bounded external receive test;
- confirm Mail Room ingestion;
- monitor before starting another domain.

## Initial migration order

1. Build disabled Edge1 gateway foundation.
2. Validate local-only SMTP ingestion on Edge1.
3. Prepare `mail.ww.cx` DNS/certificate/firewall change set without applying it.
4. Migrate `creekco.ca` first after explicit DNS/public-listener approval.
5. Monitor and accept.
6. Migrate `spiritcreekgardens.com`.
7. Migrate `scgardens.ca` if still required as an independent mail domain.
8. Migrate `omegafx.com`.
9. Re-evaluate `ww.cx`; default is to leave it on Namecheap Private Email.

## Rollback

For every domain, preserve the exact previous MX set and provider mailbox state until Edge1 acceptance is complete.

Rollback procedure:

1. stop/disable the affected Edge1 virtual-domain route if needed;
2. restore the previous MX records;
3. verify resolver consensus;
4. verify provider mailbox reception;
5. keep Edge1-ingested evidence for audit; do not delete messages to hide a failed migration.

## Future multi-node design

`mail.ww.cx` must remain independent of a single physical machine. A future Edge2/mail peer may be added behind the same service identity using multiple MX priorities or a fronting mail relay/load-distribution model.

Do not encode `edge1` as the permanent public mail hostname in domain policy; `mail.ww.cx` is the stable service name.

## Explicitly deferred / protected actions

The following remain unauthorized until separately approved:

- production DNS/MX changes;
- `mail.ww.cx` public DNS creation/change;
- firewall changes or opening TCP/25;
- production certificate issuance/installation;
- public SMTP listener activation;
- cancellation of Namecheap Private Email or cPanel services;
- outbound mail delivery from Edge1;
- SPF/DKIM/DMARC production changes;
- destructive mailbox/provider cleanup.
