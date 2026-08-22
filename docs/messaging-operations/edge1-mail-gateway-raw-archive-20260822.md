# Edge1 Mail Gateway — Archive-First Intake

Date: 2026-08-22
Status: implementation and validation phase; public SMTP remains disabled

## Why this phase exists

The accepted local gateway proved that Postfix can deliver one managed-domain recipient into the authoritative Mail Room store while preserving the original SMTP recipient. That direct-normalization path is not a sufficient public catch-all delivery boundary by itself: real mail can be HTML-only, contain unsupported MIME structures, or exceed the strict normalizer's current limits.

For public inbound mail, successful SMTP receipt must not depend on the knowledge-extraction parser accepting every valid message. The durable raw message is therefore the receipt authority; Mail Room normalization becomes downstream processing.

## Archive contract

Postfix invokes `tools/messaging/edge1_mail_gateway_archive.py` once per original recipient through the existing one-recipient `wwcxmail` pipe.

The archive root is:

`/var/lib/wwcx-mail-gateway/inbound`

Messages are separated by domain and recipient-specific Postfix delivery:

```text
/var/lib/wwcx-mail-gateway/inbound/
  creekco.ca/
    <queue-id>-<recipient-hash>/
      message.eml
      metadata.json
  spiritcreekgardens.com/
  scgardens.ca/
  omegafx.com/
```

Directories are mode `0700`; raw messages and metadata are mode `0600`. The runtime service account is `wwcx-mail-gateway`.

`ww.cx` is intentionally excluded from this v1 candidate-domain archive path.

## Delivery semantics

1. Validate the configured candidate domain, original recipient, and Postfix queue id.
2. Durably write the exact raw RFC822 message.
3. Durably write initial metadata with normalization status `pending`.
4. At this point raw receipt is authoritative.
5. Attempt strict Mail Room normalization.
6. Record normalization as `ingested` or `held`.
7. Return transport success for a durably archived message even if strict normalization holds it for later processing.

An exact Postfix retry with the same queue id, recipient, and raw bytes resolves to the existing archive and does not attempt a duplicate Mail Room insert.

## Raw metadata

`metadata.json` records only operational receipt evidence and untrusted-message state, including:

- contract `wwcx.edge1-mail-gateway-raw-archive.v1`;
- archive timestamp;
- managed domain;
- SMTP original recipient;
- Postfix queue id;
- RFC822 SHA-256;
- byte size;
- normalization status;
- no send/provider/mailbox mutation authority.

The raw message content itself is not emitted in acceptance evidence.

## Size boundary

The raw intake ceiling is 50 MiB and the generated Postfix configuration uses `message_size_limit = 52428800` so Postfix does not intentionally accept a message larger than the archive process is designed to read.

This is distinct from current strict Mail Room normalization limits. Messages that are acceptable to the raw archive but unsupported by normalization remain safely held with their original RFC822 preserved.

## Accepted local state before migration

The authenticated 2026-08-22 local apply established:

- repository main `01beece404a95a88827ce208216cda8b45af31d1`;
- Postfix active;
- TCP/25 at `127.0.0.1:25` only;
- `inet_interfaces = loopback-only`;
- managed virtual-domain and catch-all maps installed;
- `virtual_transport = wwcxmail:`;
- `wwcxmail_destination_recipient_limit = 1`;
- direct normalizer pipe using `${original_recipient}` and Postfix `O` flag;
- one synthetic Creekco acceptance produced exactly one new authoritative `production_native` Mail Room record;
- `rollback_performed=false`;
- no DNS/MX, firewall, TLS certificate, provider, outbound-delivery, or `ww.cx` routing change.

The Postfix warning that the chroot copy of `resolv.conf` differs from `/etc/resolv.conf` is recorded as a warning, not as acceptance failure. This gateway phase does not depend on outbound DNS resolution.

## Migration wrapper

`deploy/messaging/migrate-edge1-mail-gateway-raw-archive.sh` is restricted to the exact accepted direct-ingest state. It refuses to proceed unless:

- Postfix remains loopback-only;
- managed domain/recipient maps are the accepted WW.CX maps;
- `virtual_transport = wwcxmail:`;
- recipient limit is exactly one;
- the current pipe is the prior direct-ingest implementation;
- TCP/25 has no non-loopback listener.

The migration backs up `main.cf`, `master.cf`, current `postconf` state, listener state, and the current `wwcxmail` definition. It then creates the protected archive root, switches only the pipe transport to archive-first intake, sets the 50 MiB SMTP size boundary, checks/reloads Postfix, verifies loopback-only state, and runs the one-message local acceptance.

Any gated failure restores the backed-up Postfix configuration and reloads it. Already-durable raw archive evidence is not deleted during rollback.

## Acceptance after migration

The local acceptance now requires both:

- a domain-separated raw `message.eml` plus matching archive metadata containing the Postfix-added `X-Original-To`; and
- exactly one new authoritative `production_native` Mail Room record with the same Postfix queue correlation.

## Public-ingress boundary still closed

This phase does **not**:

- publish or modify `mail.ww.cx` DNS;
- modify any domain MX record;
- open firewall TCP/25;
- bind Postfix to the public interface;
- obtain/install a TLS certificate;
- cancel or change provider mailboxes;
- enable outbound delivery;
- migrate `ww.cx`.

After archive-first live acceptance, the next engineering phase is public-ingress readiness: DNS identity, SMTP/TLS hardening, abuse/rate controls, external reachability validation, and a single-domain cutover plan beginning with `creekco.ca`.
