# Multi-Domain Mail Provider Inventory

## Status

This document records read-only evidence captured on **2026-08-01 at 05:28:53 UTC** for the five managed mail domains. The evidence was collected from both Cloudflare and Google DNS-over-HTTPS resolvers. Their normalized MX, SPF, DMARC, and nameserver answers agreed for every domain.

The source artifact was produced by GitHub Actions workflow run `30685903870`, artifact `8813887895`, with SHA-256 digest:

```text
69a4b8620bd279be5276cf91ac4f1f0355bd968f1525f1005e4835cbd184f3e2
```

This inventory does not provision mailboxes, create aliases, change forwarders, modify DNS, authorize senders, or enable live gateway traffic.

## Canonical internal addresses

The repository defines three different internal roles:

| Address | Purpose | Public use |
|---|---|---|
| `john-inbox@ww.cx` | Private delivery destination for every managed `john@...` identity | Internal only |
| `maildesk@ww.cx` | Shared delivery destination for company and role identities | Internal only |
| `noreply@ww.cx` | Outbound-only sender for explicitly system-generated notifications | Never an inbound destination |

These definitions are authoritative for gateway design, but provider-side provisioning has not yet been proven. Neither internal delivery mailbox should be advertised or used as a public correspondent identity.

## Provider matrix

| Domain | Published inbound provider | MX state | SPF | DMARC | Current assessment |
|---|---|---|---|---|---|
| `ww.cx` | Namecheap Private Email | `mx1.privateemail.com`, `mx2.privateemail.com` | Namecheap Private Email include | Not published | Existing mail service is indicated; provider-admin inventory still required |
| `creekco.ca` | Namecheap shared hosting | Three `jellyfish.systems` MX hosts | Shared-hosting SPF present | `p=none` | Operational role addresses have passed limited round-trip tests |
| `scgardens.ca` | Namecheap shared hosting | Three `jellyfish.systems` MX hosts | Shared-hosting SPF present | `p=none` | Public DNS is mail-ready; provider-side mailbox inventory is unknown |
| `omegafx.com` | Namecheap shared hosting | Three `jellyfish.systems` MX hosts | Shared-hosting SPF present | `p=none` | Public DNS is mail-ready; provider-side mailbox inventory is unknown |
| `spiritcreekgardens.com` | None observed | No MX | Not published | Not published | Inbound mail is not ready; provider and routing decision required |

### WW.CX

Current MX records point to Namecheap Private Email:

```text
10 mx1.privateemail.com
20 mx2.privateemail.com
```

A Google Workspace onboarding notice for `techgod@ww.cx` stated that domain verification remained outstanding, and a Google account identity for `john@ww.cx` was observed. Those facts demonstrate Google account/onboarding activity but do not make Google the authoritative inbound provider. Published MX remains the controlling evidence for current inbound delivery.

Before the gateway can depend on WW.CX mail, the Namecheap Private Email control panel must be inventoried for actual mailboxes, aliases, catch-all behavior, forwarders, quotas, and sender-verification capabilities.

### CreekCo

Current MX records point to Namecheap shared hosting:

```text
5 mx1-hosting.jellyfish.systems
10 mx2-hosting.jellyfish.systems
20 mx3-hosting.jellyfish.systems
```

Limited round-trip tests on 2026-07-28 produced replies from:

- `abuse@creekco.ca`
- `contact@creekco.ca`
- `privacy@creekco.ca`
- `regulatory@creekco.ca`
- `accessibility@creekco.ca`
- `noc@creekco.ca`

The first four are already represented in the hub configuration. `accessibility@creekco.ca` and `noc@creekco.ca` were operationally observed but are not yet registered in the 35-route identity model. They should be added through a separate tested repository change before any production cutover.

The remaining configured CreekCo identities have not been proven individually. A provider export is still needed to distinguish real mailboxes from aliases or forwarders.

### Spirit Creek Gardens

`spiritcreekgardens.com` has Dyn authoritative nameservers but no published MX, SPF, or DMARC records. Namecheap support correspondence from 2026-07-18 through 2026-07-21 documented unresolved addon-domain authentication while external Dyn DNS remained authoritative.

The primary work identity `john@spiritcreekgardens.com` therefore remains a configured identity only. It must not be represented as a currently deliverable mailbox until an inbound provider is selected, the address is provisioned, DNS is deliberately configured, and controlled tests succeed.

### Short gardens domain and OmegaFX

Both `scgardens.ca` and `omegafx.com` use the same Namecheap shared-hosting mail family as CreekCo and publish monitoring-only DMARC policies. Their provider-side mailbox, alias, and forwarder inventories have not yet been obtained.

## Authentication posture

Current public evidence shows:

- WW.CX has SPF but no observed DMARC record.
- CreekCo, the short gardens domain, and OmegaFX have SPF plus `p=none` DMARC monitoring records.
- Spirit Creek Gardens has no observed SPF or DMARC record.
- DKIM selectors and signing status remain unknown for all five domains.

No DMARC policy should be tightened until all legitimate outbound sources are inventoried, DKIM alignment is confirmed, aggregate reports are reviewed, and controlled delivery tests pass. No SPF record should be edited until provider and gateway send paths are finalized because an incomplete SPF change can break existing delivery.

## Provider-admin inventory required

Public DNS cannot prove the provider-side object model. For each provider account, export or record:

1. every mailbox and its access owner;
2. every alias, forwarder, distribution list, and catch-all rule;
3. whether the original recipient is preserved through forwarding;
4. outbound sender aliases and provider verification state;
5. SMTP/API submission endpoints and authentication method, without storing credentials in Git;
6. quotas, spam filtering, quarantine, bounce handling, and logs;
7. DKIM selectors and signing status;
8. recovery contacts, administrator access, and rollback procedure.

The resulting provider export must be reconciled against `config/messaging/inbound-mail-hub.json` and `config/messaging/mail-identities.json` before provisioning or cutover.

## Recommended migration sequence

1. Export the existing Namecheap Private Email and shared-hosting mailbox configurations without modifying them.
2. Verify whether `john-inbox@ww.cx` and `maildesk@ww.cx` already exist; otherwise prepare an exact provisioning and rollback plan.
3. Reconcile the two operational CreekCo identities that are absent from the registry.
4. Select an inbound provider for `spiritcreekgardens.com` and prepare DNS changes separately.
5. Inventory DKIM and confirm aligned sending for every intended sender identity.
6. Pilot copied or forwarded traffic for one non-critical role address while preserving the original recipient.
7. Validate private/shared separation, reply identity, duplicates, loops, bounces, quarantine, and rollback.
8. Provider-verify and allowlist individual outbound identities only after successful pilot evidence.
9. Authorize each mailbox, forwarding, DNS, and live-routing change explicitly at execution time.

## Current blockers

- Provider-admin exports have not been obtained.
- `john-inbox@ww.cx` and `maildesk@ww.cx` are not proven provisioned.
- `spiritcreekgardens.com` has no published MX.
- DKIM is not inventoried.
- WW.CX has no observed DMARC record.
- Two operational CreekCo identities remain outside the registry.
- Every live sender allowlist is empty and all inbound/outbound production gates remain disabled.
