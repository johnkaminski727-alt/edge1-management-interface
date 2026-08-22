# Edge1 Mail Gateway — Local-Only Intake State

Date: 2026-08-22
Status: repository implementation on feature branch; not deployed

## Parent architecture

PR #507 / main commit `65782108b25baf466b19eb505b4c130752f30225` established the disabled Edge1 Mail Gateway v1 architecture using `mail.ww.cx` as the stable service identity.

## Live read-only evidence

- Postfix is active on Edge1.
- TCP/25 is currently loopback-only at `127.0.0.1:25` according to the bounded Edge1 listener inventory.
- No public SMTP listener is part of this phase.
- The bounded Edge1 repository operator reports a detached/stale checkout and must not be used as deployment truth without reconciliation through an authenticated operator session.

## Branch implementation

- `server/mail_edge1_gateway_source.py`
- `tools/messaging/edge1_mail_gateway_ingest.py`
- `tools/messaging/render_edge1_mail_gateway_postfix.py`
- `tests/validate_edge1_mail_gateway_local_intake.py`
- `.github/workflows/edge1-mail-gateway-local-intake.yml`
- `docs/messaging-operations/edge1-mail-gateway-local-intake-20260822.md`

## Safety decisions

- Envelope RCPT recipient is authoritative for catch-all ingestion.
- Conflicting X-Original-To / Delivered-To evidence fails closed.
- Records use `edge1-mail-gateway-smtp` + authoritative `production_native` provenance.
- `ww.cx` is excluded from the local candidate-domain map.
- Generated Postfix fragments remain `inet_interfaces = loopback-only`.
- Renderer refuses any config that enables public SMTP, production MX changes, or outbound delivery.
- No secrets are required for locally delivered Edge1 SMTP mail.

## Next steps

1. Merge only if dedicated CI, repository validation, and Edge1 Operator Validation pass.
2. Reconcile live Edge1 checkout through authenticated operator session before deployment.
3. Render Postfix fragments into staging and inspect against live config.
4. Obtain operator approval for local-only Postfix configuration changes if needed.
5. Perform loopback SMTP acceptance and relay-denial tests.
6. Stop before DNS/firewall/certificate/public-listener activation.
