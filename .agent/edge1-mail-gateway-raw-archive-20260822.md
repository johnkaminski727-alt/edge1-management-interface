# Edge1 Mail Gateway — Raw Archive State

Date: 2026-08-22
Status: implementation branch; awaiting CI/merge and authenticated live migration

## Verified live parent state

Authenticated operator output at 2026-08-22 07:54 UTC verified:

- main `01beece404a95a88827ce208216cda8b45af31d1`;
- Postfix active;
- TCP/25 `127.0.0.1:25` only;
- `inet_interfaces=loopback-only`;
- `virtual_mailbox_domains=hash:/etc/postfix/wwcx-edge1-managed-domains`;
- `virtual_mailbox_maps=regexp:/etc/postfix/wwcx-edge1-recipient-regexp`;
- `virtual_transport=wwcxmail:`;
- `wwcxmail_destination_recipient_limit=1`;
- direct one-recipient pipe preserving `${original_recipient}`;
- one Creekco synthetic local acceptance advanced Mail Room from 3 to 4 records;
- accepted record source `edge1-mail-gateway-smtp`, scope `production_native`, authoritative true;
- rollback not performed;
- DNS/MX, public SMTP listener, firewall, certificate, provider state, outbound delivery, and `ww.cx` routing unchanged.

## New invariant

Public SMTP must not depend on strict Mail Room parsing. Raw RFC822 archival is the delivery boundary; normalization is downstream processing.

## This branch

Adds:

- `tools/messaging/edge1_mail_gateway_archive.py`;
- domain-separated raw archive under `/var/lib/wwcx-mail-gateway/inbound/<domain>/<queue-recipient>/`;
- mode 0700 directories and 0600 message/metadata files;
- exact retry idempotency;
- 50 MiB raw message boundary;
- best-effort normalization with `ingested` or `held` metadata state;
- Postfix renderer changed from direct ingest to archive-first pipe;
- local acceptance expanded to verify raw RFC822, metadata, X-Original-To, queue correlation, and Mail Room record;
- backup-first live migration wrapper that accepts only the currently verified direct-ingest state;
- dedicated validation workflow.

## Boundary

Still closed and unchanged:

- public SMTP listener;
- DNS or MX changes;
- firewall changes;
- TLS certificate changes;
- provider cancellation/mutation;
- outbound delivery;
- `ww.cx` migration.

## Next live step after merge

Run the authorization-gated raw archive migration on Edge1. It must leave TCP/25 loopback-only and produce a new local acceptance proving both raw archival and Mail Room normalization before any public-ingress work proceeds.
