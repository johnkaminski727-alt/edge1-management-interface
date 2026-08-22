# Edge1 Mail Gateway — Local-Only Apply and Acceptance

Date: 2026-08-22
Status: repository implementation; public SMTP and DNS/MX remain disabled

## Purpose

Apply the already-reviewed Edge1 Mail Gateway virtual-domain configuration to the existing Postfix instance while keeping TCP/25 loopback-only, then prove one complete local SMTP -> Postfix pipe -> Mail Room `production_native` ingestion.

This phase is deliberately not a public mail activation.

## Reviewed live preflight

Authenticated operator preflight on 2026-08-22 established:

- repository main synchronized to `16dfcbbc19411d66166f12140b4b26c586eaa739` before this implementation branch;
- Postfix active;
- TCP/25 listening only on `127.0.0.1:25`;
- `virtual_mailbox_domains=$virtual_mailbox_maps`;
- `virtual_mailbox_maps` empty;
- `virtual_transport=virtual`;
- no active competing virtual mailbox map was present.

Those virtual settings are treated as the known Postfix default placeholders. Any materially different live state causes the apply script to stop.

## Recipient-attribution hardening

The local pipe contract now requires:

- `wwcxmail_destination_recipient_limit = 1`;
- Postfix pipe flag `O`, which prepends `X-Original-To` for independent recipient evidence;
- `${original_recipient}` passed to Mail Room instead of `${recipient}`;
- Mail Room continues to reject any `X-Original-To` / `Delivered-To` evidence that conflicts with the supplied authoritative SMTP recipient.

This prevents a multi-recipient delivery request from becoming ambiguous and preserves the address actually presented to the gateway.

## Apply command

Run only from an authenticated Edge1 operator session after reconciling the repository to the merged commit:

```sh
sudo /opt/edge1-management-interface/deploy/messaging/apply-edge1-mail-gateway-local.sh \
  --authorization WWCX-EDGE1-MAIL-GATEWAY-LOCAL-APPLY-001 \
  --execute
```

## Apply behavior

Before mutation the script:

1. verifies the repository is on clean `main`;
2. renders and re-validates the safely-disabled gateway configuration;
3. verifies TCP/25 is loopback-only;
4. verifies the existing virtual-domain settings match the reviewed default placeholders;
5. refuses pre-existing WW.CX-managed map paths or a pre-existing `wwcxmail` master service;
6. creates a root-only backup/evidence directory under `/var/backups/wwcx-mail-gateway/`.

It then:

1. installs the managed-domain hash source and recipient regexp map;
2. builds the hash map with `postmap`;
3. sets only the local virtual-domain parameters required by the gateway;
4. creates the `wwcxmail` pipe transport;
5. runs `postfix check` and explicit map queries;
6. reloads Postfix;
7. verifies TCP/25 is still loopback-only;
8. runs one synthetic local-only acceptance as `wwcx-mail-gateway` against `127.0.0.1:25`;
9. verifies exactly one Mail Room record was added with authoritative `production_native` provenance and Postfix queue correlation;
10. writes before/after evidence and SHA-256 hashes.

## Automatic rollback

Once mutation begins, failure arms automatic rollback. The script restores the backed-up `main.cf` and `master.cf`, removes only the newly created WW.CX map files, checks Postfix, and reloads the restored configuration.

The synthetic Mail Room acceptance record is not deleted if Postfix rollback occurs; correspondence deletion is intentionally outside this apply path.

## Still not authorized or performed

This phase does not:

- publish or change `mail.ww.cx` DNS;
- change any production MX record;
- open TCP/25 on a public or WireGuard interface;
- change firewall rules;
- obtain or change certificates;
- cancel Namecheap Private Email or cPanel mail;
- enable outbound delivery;
- migrate `ww.cx`;
- send mail to an external host.

## Candidate domains

Local virtual-domain preparation covers:

1. `creekco.ca`;
2. `spiritcreekgardens.com`;
3. `scgardens.ca`;
4. `omegafx.com`.

`ww.cx` remains external during v1 rollout.

## Next boundary

After local apply acceptance succeeds, the next phase is public-ingress readiness for `mail.ww.cx`: authoritative DNS target design, certificate/public SMTP controls, anti-abuse policy, and a single-domain MX migration plan beginning with `creekco.ca`.

Those production DNS/public-listener actions remain separate approval gates.
