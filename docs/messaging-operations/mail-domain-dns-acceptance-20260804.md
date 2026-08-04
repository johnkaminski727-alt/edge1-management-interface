# Five-domain mail DNS acceptance — 2026-08-04

## Evidence

A fresh read-only GitHub Actions capture completed at `2026-08-04T00:31:11Z` using Cloudflare and Google DNS-over-HTTPS resolvers.

Accepted source:

- workflow run: `30865819181`;
- artifact: `8876043654`;
- artifact name: `mail-domain-inventory-75539a311ed6a55da669b191e85fbb1ccf079b40`;
- artifact SHA-256: `002a11bab88c2c2d71de24ca94069650f32bd656356ab264c6e0f92d0329acd2`;
- source commit: `3c0997d25411e09f135e06325f47d09268b4f931`.

The normalized acceptance record is:

```text
records/messaging/dns-inventories/mail-domain-dns-acceptance-20260804.json
```

Both resolvers agreed on MX, SPF, DMARC, and authoritative nameserver answers for all five managed domains.

## Comparison with the accepted August 1 snapshot

The fresh public DNS answers match the canonical accepted snapshot in `config/messaging/mail-provider-inventory.json`.

### WW.CX

- MX remains Namecheap Private Email:
  - `10 mx1.privateemail.com`;
  - `20 mx2.privateemail.com`.
- SPF remains `v=spf1 include:spf.privateemail.com ~all`.
- No DMARC record was observed.
- Dyn remains authoritative.

The provider-reported default DKIM selector is not independently verified by this capture because the current inventory workflow does not guess selector labels. DKIM signing and alignment remain a separate provider/DNS evidence requirement.

### CreekCo, SC Gardens, and OmegaFX

All three shared-hosting domains retain:

- the three `jellyfish.systems` MX hosts;
- shared-hosting SPF including `162.0.217.71` and `spf.web-hosting.com`;
- DMARC monitoring policy `v=DMARC1; p=none;`;
- Namecheap shared-hosting authoritative nameservers.

A monitoring-only DMARC record is not proof that every intended sender is DKIM- or SPF-aligned. No policy tightening is authorized.

### Spirit Creek Gardens

`spiritcreekgardens.com` still has:

- no published MX record;
- no published SPF record;
- no published DMARC record;
- Dyn authoritative nameservers.

It remains not ready for inbound or outbound mail. Selecting a provider and changing DNS are separate production and credential decisions.

## Gateway effect

None. This is read-only public DNS evidence. It did not:

- change DNS or nameservers;
- log into a provider;
- install credentials;
- provision a mailbox;
- enable a sender or provider;
- enable the send endpoint or external delivery;
- prepare or send a message.

## Next evidence required

The DNS capture confirms stability, not delivery readiness. Remaining authentication work includes:

1. independently identify and query the intended DKIM selector for the first pilot sender;
2. prove provider-side signing and domain alignment;
3. define the envelope sender and return-path;
4. review DMARC aggregate-report handling before any policy change;
5. verify SPF coverage for the exact chosen outbound path;
6. retain the existing no-change posture until one provider, one sender, one controlled recipient, and one exact message are separately authorized.
