# Edge1 Mail Gateway — Local-Only Intake Phase

Date: 2026-08-22
Status: implementation preparation; public activation prohibited

## Purpose

Prove the new Edge1 mail path without changing DNS or exposing SMTP publicly.

Live Edge1 already has Postfix active on loopback TCP/25. This phase keeps that posture and builds a deterministic local transport from an MTA-accepted SMTP envelope into the existing Mail Room correspondence store.

## Components

- `server/mail_edge1_gateway_source.py`
  - parses raw RFC822 bytes;
  - treats the SMTP envelope recipient as authoritative;
  - validates any `X-Original-To` / `Delivered-To` evidence against the envelope;
  - persists as authoritative `production_native` source `edge1-mail-gateway-smtp`;
  - performs no network activity.

- `tools/messaging/edge1_mail_gateway_ingest.py`
  - local CLI/pipe target;
  - accepts RFC822 from stdin or a local file;
  - permits only candidate domains from `edge1-mail-gateway-v1.json`;
  - refuses `ww.cx` because v1 keeps it external;
  - emits sanitized hashed evidence only.

- `tools/messaging/render_edge1_mail_gateway_postfix.py`
  - generates Postfix maps/fragments from the disabled gateway config;
  - refuses public activation settings;
  - renders `inet_interfaces = loopback-only`;
  - renders relay-denial requirements and candidate-domain maps;
  - writes files only to an explicit output directory and never edits `/etc/postfix`.

## Intended local Postfix model

Generated `main.cf.fragment` includes:

```text
inet_interfaces = loopback-only
smtpd_recipient_restrictions = permit_mynetworks,reject_unauth_destination
relay_domains =
virtual_mailbox_domains = hash:/etc/postfix/wwcx-edge1-managed-domains
virtual_mailbox_maps = regexp:/etc/postfix/wwcx-edge1-recipient-regexp
virtual_transport = wwcxmail:
```

Generated `master.cf.fragment` defines a local pipe transport running as `wwcx-mail-gateway` and passing Postfix `${recipient}` and `${queue_id}` to the ingestion CLI.

These are preparation fragments, not an installer or activation authorization.

## Recipient authority

Catch-all mail must preserve the SMTP envelope recipient exactly.

Example:

```text
RCPT TO:<vendor-2026@creekco.ca>
To: Accounts Department <accounts@some-visible-domain.example>
```

Mail Room recipient authority is `vendor-2026@creekco.ca`, not the visible `To` header.

If provider/MTA-added `X-Original-To` or `Delivered-To` evidence conflicts with the SMTP envelope recipient, ingestion fails closed so Postfix can retain/retry or quarantine rather than misfile the message.

## Provenance

Successful local gateway records use:

```json
{
  "source": "edge1-mail-gateway-smtp",
  "scope": "production_native",
  "authoritative": true
}
```

The record remains untrusted content and grants neither mutation nor sending authority.

## Relay safety

The prepared Postfix model must never become an open relay.

Before live installation/activation, acceptance must prove:

- unmanaged-domain recipients are rejected;
- `ww.cx` is not accepted by the Edge1 v1 virtual-domain map;
- candidate-domain arbitrary local parts are accepted only as local destinations;
- remote relay destinations are rejected;
- outbound SMTP delivery is not enabled by the gateway transport.

## Local-only acceptance plan

After an authenticated Edge1 operator reconciles the live checkout with current `main`:

1. render fragments into an isolated staging directory;
2. inspect current Postfix configuration and back it up;
3. compare fragments against live settings;
4. if explicitly approved for local-only installation, install candidate-domain maps while preserving `inet_interfaces = loopback-only`;
5. inject a synthetic/local SMTP message through `127.0.0.1:25` to an approved candidate-domain address;
6. confirm exactly one `production_native` Mail Room record and exact original-recipient preservation;
7. test unmanaged-domain relay denial;
8. capture sanitized evidence;
9. rollback if any invariant fails.

This phase does not require external delivery or DNS changes.

## Protected next boundary

Do not proceed from local acceptance to public SMTP until there is explicit approval for the exact DNS/firewall/certificate/public-listener actions.
