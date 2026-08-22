# Edge1 Mail Gateway — Local Apply State

Date: 2026-08-22
Status: implementation branch; awaiting CI/merge and authenticated operator execution

## Parent milestones

- #507: disabled Edge1 Mail Gateway v1 architecture.
- #508: local SMTP -> Mail Room intake and safe renderer.
- #509: read-only Postfix preflight.
- #510: preflight Postfix admin-tool PATH fallback.

## Live preflight accepted

Operator evidence showed:

- Postfix active;
- TCP/25 loopback-only at `127.0.0.1:25`;
- no active `virtual_mailbox_maps`;
- default placeholder `virtual_mailbox_domains=$virtual_mailbox_maps`;
- default `virtual_transport=virtual`.

## This phase

Adds:

- one-recipient `wwcxmail` pipe delivery;
- `${original_recipient}` as authoritative Mail Room recipient;
- Postfix `O` flag for `X-Original-To` cross-check evidence;
- backup-first local apply with automatic Postfix rollback on failure;
- one synthetic 127.0.0.1-only SMTP acceptance executed as `wwcx-mail-gateway`;
- acceptance proof requiring exactly one new authoritative `production_native` record;
- exact Postfix queue correlation;
- dedicated CI.

## Boundary

The apply keeps `inet_interfaces=loopback-only` and does not change DNS, MX, firewall, TLS certificates, provider state, outbound delivery, or `ww.cx` routing.

After local acceptance, public `mail.ww.cx` ingress and the first `creekco.ca` MX cutover remain separate production authorization steps.
