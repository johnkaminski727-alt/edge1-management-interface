# Edge1 Mail Gateway — Public Ingress Readiness

Date: 2026-08-22

## Purpose

Prepare evidence for a future Internet-facing `mail.ww.cx` SMTP listener without activating it.

This phase follows successful local archive-first acceptance. The current delivery boundary is:

`Postfix -> durable raw RFC822 archive -> best-effort Mail Room normalization`

The raw archive is authoritative for receipt. A normalization failure must not erase an otherwise accepted RFC822 message.

## Current accepted live state

The authenticated operator migration completed successfully on 2026-08-22 at approximately 08:29Z:

- Postfix remained active;
- TCP/25 remained loopback-only;
- `wwcxmail` migrated to `edge1_mail_gateway_archive.py`;
- one Creekco synthetic message was archived and normalized;
- raw archive verification succeeded;
- Mail Room advanced from 4 records to 5;
- provenance remained `edge1-mail-gateway-smtp`, `production_native`, authoritative;
- rollback was not performed;
- evidence directory: `/var/backups/wwcx-mail-gateway/raw-archive-migration-20260822T082911Z`.

No DNS/MX, firewall, certificate, provider, outbound-delivery, or `ww.cx` routing change was made.

## Read-only readiness preflight

Run:

```sh
sudo bash deploy/messaging/prepare-edge1-mail-gateway-public-readiness.sh
```

The script writes a protected evidence directory under `/tmp` and prints its path. It does not fetch or change Git, edit Postfix, reload services, modify firewall rules, request certificates, or change DNS.

It fails closed if the pre-activation safety model has drifted, including:

- TCP/25 already exposed outside loopback;
- Postfix not active;
- archive-first transport not active;
- recipient limit not equal to one;
- managed domain maps not equal to the accepted configuration;
- `relay_domains` not empty;
- `reject_unauth_destination` missing;
- message size boundary not equal to 50 MiB;
- raw archive root ownership/mode not `wwcx-mail-gateway:wwcx-mail-gateway 0700`;
- `ww.cx` no longer marked `stay_external`.

## Evidence collected

The preflight records:

- repository branch/head and dirty state;
- interface and route state;
- current TCP listeners and TCP/25 classification;
- relevant Postfix values and the `wwcxmail` master transport;
- raw archive and Mail Room storage metadata;
- filesystem free-space evidence;
- Postfix queue state when `postqueue` is available;
- `mail.ww.cx` IPv4 lookup;
- reverse DNS/PTR for the public IPv4 selected by the default route;
- forward-confirmation of that PTR hostname;
- existence and SAN metadata for a `mail.ww.cx` Let's Encrypt certificate when present;
- read-only nftables ruleset evidence when `nft` is available.

The preflight never reads or prints a TLS private key. It checks only file metadata for the key and parses the public certificate.

## DNS and PTR criteria

`mail.ww.cx` is the stable service identity. Before public activation, its A record should resolve to the current Edge1 public IPv4.

A reverse-DNS PTR must exist for that IPv4 and forward-confirm back to the same address. The PTR does not have to equal `mail.ww.cx`; for inbound-only service it may remain another stable Edge1 hostname if forward-confirmed and operationally intentional. If outbound SMTP is later enabled, EHLO/PTR/reputation alignment must be reviewed as its own project.

## TLS criteria

Before advertising STARTTLS publicly, a certificate valid for `mail.ww.cx` should be installed and Postfix TLS configuration should be reviewed. Certificate issuance or installation is a privileged production change and is not part of this readiness phase.

## Public activation gates

The following remain separate actions requiring explicit production authorization:

1. DNS A/AAAA change for `mail.ww.cx`, if needed.
2. Reverse-DNS/PTR provider change, if needed.
3. TLS certificate issuance/installation, if needed.
4. Exact Postfix public listener/bind change.
5. Firewall change required for inbound TCP/25.
6. External TCP/25 reachability and SMTP relay-denial probe after exposure.
7. First production MX cutover, starting with `creekco.ca`.

An external probe must occur after the listener becomes reachable but before a production MX record points at it.

## Domain migration order

The v1 order remains:

1. `creekco.ca`
2. `spiritcreekgardens.com`
3. `scgardens.ca` if independently required
4. `omegafx.com`

`ww.cx` remains external during v1. The existing Namecheap path and Mail Room connector remain migration/rollback infrastructure.

## Outbound-mail separation

The existing WW.CX outbound-mail gateway is a separate disabled foundation on loopback. Public inbound readiness must not enable its providers, send endpoint, external preparation, live delivery, or SMTP cutover controls.

## Rollback principle

Do not remove provider mailboxes or fallback paths before a migrated domain passes public acceptance. For the first domain, preserve the prior MX values and provider state until Edge1 has demonstrated receipt of real external messages, raw archive durability, Mail Room ingestion/held behavior, and operational monitoring.
