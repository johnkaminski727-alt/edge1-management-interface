# Namecheap Private Email inventory acceptance — WW.CX

Evidence date: 2026-08-02  
Recorded: 2026-08-04  
Provider ticket: `NC-JDV-2953`

## Accepted provider-visible facts

Namecheap Private Email support confirmed the following read-only facts for `ww.cx`:

- the subscription is the Pro Private Email plan;
- the subscription was active through November 14, 2026 at the evidence date;
- the plan includes three mailbox slots;
- two mailboxes exist and are active:
  - `blank@ww.cx`;
  - `domaincontact@ww.cx`;
- one mailbox slot was unused;
- neither mailbox had an alias;
- Catch-All was enabled with destination `blank@ww.cx`;
- each mailbox had a 10 GB quota;
- approximate use at capture was 130 MB for `blank@ww.cx` and less than 1 MB for `domaincontact@ww.cx`;
- the provider reported the domain configured correctly for send and receive;
- the provider reported MX, SPF and DKIM configured for Private Email;
- the subscription used the provider's default DKIM selector;
- Private Email aliases are receive/forward identities and cannot send as the alias address.

The accepted normalized record is:

`records/messaging/provider-inventories/namecheap-private-email-wwcx-20260802.json`

## Conservative classifications

Both observed mailboxes are classified with access class `unknown`. The support response did not establish who has access or whether either mailbox is the intended canonical private or shared delivery destination.

The normalized `can_send=true` value records the provider statement that the active mailbox service and domain are configured for sending and receiving. It does not claim that an authenticated send test, From-address policy test, DKIM alignment test, or production delivery test has occurred.

The provider-side routing mode remains `unknown`. Public MX and provider service status do not prove the hosting-side routing setting requested by the reconciliation contract.

## Explicit unresolved items

Namecheap support could not inspect mailbox-level settings from its support view. The following remain unverified and must not be inferred:

- auto-forward enabled or disabled for either mailbox;
- auto-forward destination;
- whether a forwarded message is retained at the provider;
- enabled or disabled filter rules;
- filter actions that redirect, discard or modify delivery;
- mailbox access owners;
- authoritative hosting-side routing mode;
- authenticated sender behavior and From-address restrictions;
- exact public DKIM selector label and independent DNS verification;
- whether `john-inbox@ww.cx` or `maildesk@ww.cx` exists;
- whether either observed mailbox should be retained, renamed, migrated or used as a destination.

These gaps require read-only review inside each Private Email webmail account and separate hosting-side routing evidence. No mailbox login, provider change, provisioning, deletion, forwarding, filter, DNS or sender action is authorized by this record.

## Reconciliation effect

This evidence closes the prior lack of a substantive WW.CX provider-visible mailbox inventory. It does not make the combined provider reconciliation ready for pilot because:

- the canonical internal mailboxes are not observed;
- the two observed `ww.cx` mailboxes are unexpected relative to the canonical route model;
- Catch-All is a non-reject default-address warning;
- routing remains unknown;
- mailbox access and forwarding/filter state remain unresolved;
- most canonical public identities are not represented as provider objects.

## Secret handling

No support PIN, password, token, reset link, session URL, cookie, private key, message body, raw email export or provider credential is stored in the normalized record or this acceptance document.
