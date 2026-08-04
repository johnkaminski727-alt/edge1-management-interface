# WW.CX DKIM DNS acceptance — 2026-08-04

## Accepted evidence

The read-only DKIM candidate workflow completed successfully at `2026-08-04T00:44:53Z`.

Source:

- workflow run: `30866538424`;
- artifact: `8876301894`;
- artifact name: `mail-dkim-inventory-70aaaf1d8ddb06c7ad7212e561fda3433c14b78c`;
- artifact SHA-256: `9cf22e2e3c643c24e151580865ecf5e7785dfd2678fe0f40376c3cff4432b315`;
- inventory-file SHA-256 from the artifact manifest: `d5b867a893a07628432de2cd5962a99db498ab03fed8a9b92f54283b217d7d6d`;
- source commit: `8458f02398d450f92a720e0fe4aab1f91f06563e`;
- resolvers: Cloudflare and Google DNS-over-HTTPS.

The minimized acceptance record is:

```text
records/messaging/dns-inventories/wwcx-dkim-dns-acceptance-20260804.json
```

## Result

Both resolvers agreed that:

- `default._domainkey.ww.cx` publishes one DKIM-shaped RSA TXT record;
- the normalized record is 408 characters;
- the public-key tag is non-empty and 392 characters;
- the minimized record SHA-256 is `3c38973128024f7e0892c6dd7420b6fd144019c0660f80c29eff917cfc6b7962`;
- `privateemail._domainkey.ww.cx` is not observed and returns DNS status 3.

This is consistent with Namecheap support's statement that the WW.CX subscription uses the default DKIM selector and with Namecheap's published legacy-selector documentation.

The acceptance record does not store the public key. It stores only the record hash, lengths, key type, structural result, query names, and resolver-consensus metadata.

## What this proves

The evidence proves that a structurally valid public DKIM record is visible at the `default` candidate selector for `ww.cx`.

## What this does not prove

The evidence does not prove that:

- Namecheap currently signs outgoing WW.CX messages;
- the provider uses selector `default` on an actual sent message;
- the `d=` signing domain aligns with the visible From domain;
- SPF aligns with the envelope sender;
- DMARC passes;
- a particular WW.CX mailbox is authorized to send;
- a gateway message was accepted or delivered.

Accordingly:

```text
provider_signing_verified=false
header_alignment_verified=false
ready_for_sender_activation=false
message_sent=false
```

## Remaining DKIM gate

The remaining DKIM gate requires one separately authorized controlled pilot message to a WW.CX-controlled test inbox after provider credentials, sender identity, return-path, bounce/complaint handling, and all gateway activation controls are ready.

The complete received headers must then prove:

1. `DKIM-Signature` contains `s=default`;
2. the signing domain aligns with the visible From domain;
3. the DKIM result passes at the receiving system;
4. SPF and envelope alignment are understood;
5. DMARC result and policy are recorded;
6. provider message ID and gateway audit record link to the same pilot.

## Preserved boundaries

This acceptance did not log into Namecheap, read a credential, expose the public key, change DNS, enable a provider or sender, activate the gateway, prepare a message, or send a message.
