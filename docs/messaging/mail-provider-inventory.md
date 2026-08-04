# Multi-Domain Mail Provider Inventory

## Status

This document reconciles two accepted read-only evidence sets:

1. the five-domain public DNS inventory captured on **2026-08-01 at 05:28:53 UTC** from Cloudflare and Google DNS-over-HTTPS resolvers; and
2. provider-side inventory evidence accepted through **2026-08-02** for Namecheap shared hosting and WW.CX Namecheap Private Email.

The DNS artifact was produced by GitHub Actions workflow run `30685903870`, artifact `8813887895`, with SHA-256 digest:

```text
69a4b8620bd279be5276cf91ac4f1f0355bd968f1525f1005e4835cbd184f3e2
```

The accepted WW.CX Private Email record is:

```text
records/messaging/provider-inventories/namecheap-private-email-wwcx-20260802.json
```

This inventory does not provision or remove mailboxes, create aliases, change forwarders or filters, modify DNS, install credentials, authorize senders, or enable live gateway traffic.

## Canonical internal addresses

The repository defines three internal roles:

| Address | Purpose | Public use | Provider observation |
|---|---|---|---|
| `john-inbox@ww.cx` | Private delivery destination for managed `john@...` identities | Internal only | Not observed |
| `maildesk@ww.cx` | Shared delivery destination for company and role identities | Internal only | Not observed |
| `noreply@ww.cx` | Outbound-only system sender | Never an inbound destination | Not observed |

Neither internal delivery mailbox should be advertised or used as a public correspondent identity. The absence of a provider object means no routing or sender assumption may be made.

## Provider matrix

The public DNS columns below describe the accepted 2026-08-01 snapshot, not a claim that records have remained unchanged since capture.

| Domain | Published inbound provider | Accepted provider-side evidence | Authentication evidence | Current assessment |
|---|---|---|---|---|
| `ww.cx` | Namecheap Private Email | Two active mailboxes, no aliases, Catch-All to `blank@ww.cx` | Provider reports MX, SPF and default-selector DKIM configured; no DMARC observed in DNS snapshot | Provider-visible inventory accepted but canonical internal mailboxes, forwarding, filters, routing and sender alignment remain unresolved |
| `creekco.ca` | Namecheap shared hosting | Seven active mailboxes observed; six match canonical identities; `main@creekco.ca` unexpected | Shared-hosting SPF and `p=none` DMARC in DNS snapshot; DKIM alignment not accepted | Partial provider inventory accepted; routing and full sender capability remain unresolved |
| `scgardens.ca` | Namecheap shared hosting | No canonical mailbox or forwarder objects observed in accepted capture | Shared-hosting SPF and `p=none` DMARC in DNS snapshot; DKIM alignment not accepted | Public DNS indicates mail service, but provider objects required by the canonical route model are missing |
| `omegafx.com` | Namecheap shared hosting | No canonical mailbox or forwarder objects observed in accepted capture | Shared-hosting SPF and `p=none` DMARC in DNS snapshot; DKIM alignment not accepted | Public DNS indicates mail service, but provider objects required by the canonical route model are missing |
| `spiritcreekgardens.com` | None observed in DNS snapshot | No provider object inventory | No MX, SPF or DMARC observed in DNS snapshot | Inbound and outbound mail remain unproven; provider and deliberate DNS decision required |

## WW.CX Private Email

Namecheap support ticket `NC-JDV-2953` established the following provider-visible state at the evidence date:

- Pro Private Email subscription;
- subscription active through November 14, 2026 at capture;
- three mailbox slots included;
- two active mailboxes:
  - `blank@ww.cx`;
  - `domaincontact@ww.cx`;
- one unused mailbox slot;
- no aliases on either mailbox;
- Catch-All forwarding to `blank@ww.cx`;
- 10 GB quota for each mailbox;
- approximately 130 MB used by `blank@ww.cx` and less than 1 MB used by `domaincontact@ww.cx` at capture;
- provider-reported domain configuration for sending and receiving;
- provider-reported MX, SPF and DKIM configuration using the default DKIM selector;
- provider aliases can receive or forward but cannot send as the alias address.

The two mailboxes are conservatively classified with access class `unknown`. Neither is treated as `john-inbox@ww.cx`, `maildesk@ww.cx`, or an approved public sender.

Namecheap support could not inspect mailbox-level auto-forward and filter settings. The following remain unknown until a read-only review is performed inside each mailbox account:

- auto-forward enabled state and destination;
- whether forwarded mail is retained;
- enabled or disabled filter rules;
- redirect, discard or modification actions;
- access ownership;
- authenticated From-address behavior.

The authoritative hosting-side routing mode also remains unknown. Public MX records and provider service status do not substitute for that evidence.

## Shared-hosting inventory

The accepted shared-hosting capture identified seven active CreekCo mailboxes. Six correspond to canonical CreekCo identities and `main@creekco.ca` remains an unexpected retained-pending-review object.

The accepted capture found no account forwarders, domain forwarders, filters or autoresponders, and unknown recipients were rejected for `creekco.ca`, `scgardens.ca`, and `omegafx.com`. Hosting-side routing modes and complete sender capabilities remain unproven.

Limited round-trip tests on 2026-07-28 produced replies from:

- `abuse@creekco.ca`;
- `contact@creekco.ca`;
- `privacy@creekco.ca`;
- `regulatory@creekco.ca`;
- `accessibility@creekco.ca`;
- `noc@creekco.ca`.

A reply demonstrates limited operational use, not the full provider object type, access owner, DKIM alignment, forwarding state, or authorization for gateway delivery.

## Spirit Creek Gardens

The accepted DNS snapshot showed Dyn authoritative nameservers and no published MX, SPF or DMARC records for `spiritcreekgardens.com`. Earlier Namecheap support correspondence documented unresolved addon-domain authentication while external Dyn DNS remained authoritative.

The configured identity `john@spiritcreekgardens.com` must not be represented as a currently deliverable mailbox until a provider is selected, the address is provisioned, DNS is deliberately configured, and controlled tests succeed.

## Authentication posture

Accepted evidence currently establishes:

- WW.CX: provider reports Private Email MX, SPF and default-selector DKIM configured; the DNS snapshot did not observe DMARC;
- CreekCo, `scgardens.ca`, and OmegaFX: shared-hosting SPF plus monitoring-only `p=none` DMARC in the DNS snapshot;
- Spirit Creek Gardens: no SPF or DMARC in the DNS snapshot;
- no managed domain yet has complete independently accepted SPF authorization, DKIM signing and alignment, DMARC review, return-path definition, and controlled gateway delivery evidence.

No DMARC policy should be tightened until all legitimate outbound sources are inventoried, DKIM alignment is independently confirmed, aggregate reports are reviewed, and controlled delivery tests pass. No SPF record should be edited until the provider and gateway send paths are finalized because an incomplete SPF change can disrupt existing delivery.

## Reconciliation state

The normalized WW.CX inventory intentionally produces warnings and critical gaps:

- `blank@ww.cx` and `domaincontact@ww.cx` are unexpected managed addresses relative to the canonical route model;
- Catch-All is a non-reject default-address warning;
- WW.CX domain routing is unresolved;
- `john-inbox@ww.cx` and `maildesk@ww.cx` are not observed;
- most canonical public identities are not represented as provider objects;
- sender capability for canonical identities is not proven.

The combined provider reconciliation is therefore **not ready for pilot**.

## Remaining provider-admin evidence

The following read-only evidence is still required:

1. mailbox access ownership and recovery ownership;
2. auto-forward settings, destinations, and retained-copy behavior for both WW.CX mailboxes;
3. all enabled and disabled WW.CX mailbox filters;
4. hosting-side routing mode for every managed domain;
5. provider-side object type and sender capability for every intended public identity;
6. exact DKIM selector labels and independent DNS/signing verification;
7. return-path, bounce, complaint, suppression, quarantine and log behavior;
8. exact rollback objects before any later mailbox, alias, forwarding or routing mutation.

## Recommended sequence

1. Complete read-only WW.CX webmail forwarding and filter inspection.
2. Capture hosting-side routing modes for all shared-hosting domains and WW.CX where applicable.
3. Complete the strict combined provider-object reconciliation.
4. Decide whether the unexpected `blank@ww.cx`, `domaincontact@ww.cx`, and `main@creekco.ca` objects should be retained, migrated, renamed or retired; do not mutate them during evidence review.
5. Prepare an exact provisioning and rollback plan for `john-inbox@ww.cx` and `maildesk@ww.cx` if they remain absent.
6. Select one outbound provider and one named pilot sender.
7. Verify SPF, DKIM, DMARC, return-path, bounce and complaint handling for that sender.
8. Authorize one controlled recipient and one exact pilot message only after all readiness gates pass.

## Current blockers

- `john-inbox@ww.cx` and `maildesk@ww.cx` are not proven provisioned.
- WW.CX forwarding, filter, access-owner and routing state remain unknown.
- Shared-hosting routing modes and full sender capabilities remain unproven.
- `spiritcreekgardens.com` had no published MX in the accepted DNS snapshot.
- Independent DKIM alignment and return-path evidence are incomplete.
- Bounce, complaint and suppression handling are undefined.
- Every live sender allowlist is empty and all inbound/outbound production gates remain disabled.
