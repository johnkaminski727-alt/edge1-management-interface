# WW.CX DKIM candidate discovery

Date: 2026-08-04

## Objective

Measure whether a public DKIM TXT record is visible at either documented Namecheap Private Email selector for `ww.cx`, without assuming the subscription generation, logging into Namecheap, changing DNS, inspecting credentials, activating a sender, or sending mail.

Namecheap's current documentation distinguishes two Private Email selector names:

- `default._domainkey` for subscriptions purchased before June 2, 2026;
- `privateemail._domainkey` for subscriptions purchased on or after June 2, 2026.

The accepted provider response for WW.CX described the service as using the default DKIM selector, but the subscription generation and exact public hostname have not been independently proven. The candidate configuration therefore queries both names and marks neither as authoritative for activation.

Official references reviewed on 2026-08-04 are recorded in:

```text
config/messaging/mail-dkim-selector-candidates.json
```

## Tool

```sh
python3 tools/messaging/mail_dkim_inventory.py \
  --pretty \
  --output /tmp/wwcx-dkim-inventory.json
```

The tool queries Cloudflare and Google DNS-over-HTTPS resolvers for:

```text
default._domainkey.ww.cx
privateemail._domainkey.ww.cx
```

It records resolver status and consensus while minimizing any public key to:

- SHA-256 of the normalized TXT record;
- normalized record character count;
- key type;
- public-key character count;
- presence and structural-shape flags.

It does not store the public key itself in the normalized evidence.

## Interpretation

Possible candidate states include:

- `published_valid_shape` — both resolvers agree on a DKIM-shaped record containing a non-empty public-key tag;
- `published_malformed_shape` — a DKIM version tag is visible but the record lacks a usable public-key shape;
- `not_observed` — both resolvers answer successfully and no TXT record is observed at that candidate;
- `non_dkim_txt_observed` — TXT data exists but does not identify itself as DKIM;
- `resolver_disagreement` — resolver answer sets differ;
- `query_failed` — neither resolver returned usable evidence.

A `published_valid_shape` result proves only that a candidate public DNS record exists. It does **not** prove:

- the provider currently signs outgoing WW.CX messages with that selector;
- the signing domain aligns with the visible From domain;
- SPF aligns with the return-path;
- DMARC passes;
- the intended sender identity is provider-authorized;
- a message was accepted, delivered, or received;
- sender activation is safe.

For that reason, every inventory result keeps:

```text
provider_signing_verified=false
header_alignment_verified=false
ready_for_sender_activation=false
```

## Workflow evidence

The dedicated workflow runs unit/static validation, captures current public evidence, and uploads an artifact:

```text
.github/workflows/capture-mail-dkim-inventory.yml
```

The capture uses no repository secret and no provider credential.

## Required follow-up after a published candidate

1. Confirm the exact selector inside the Namecheap Private Email control panel through a separately authorized authenticated session.
2. Send one separately authorized controlled pilot message only after provider, sender, return-path, bounce, complaint, SPF, DMARC, and gateway gates are ready.
3. Preserve the complete received headers from a WW.CX-controlled test inbox.
4. Verify `DKIM-Signature` selector and signing domain, SPF result and envelope domain, DMARC alignment, provider message ID, and gateway audit linkage.
5. Keep the live sender disabled if any value differs from the accepted DNS/provider plan.

## Preserved boundaries

This discovery package does not authorize or perform DNS changes, provider login, key generation, key rotation, credential handling, sender activation, provider activation, gateway activation, delivery, or message traffic.
