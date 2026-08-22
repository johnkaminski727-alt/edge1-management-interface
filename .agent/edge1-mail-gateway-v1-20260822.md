# Edge1 Mail Gateway v1 — Agent State

Date: 2026-08-22
Status: repository preparation in progress; production activation prohibited

## Objective

Prepare `mail.ww.cx` as the stable Edge1-managed inbound mail service identity for selected WW.CX-related domains while leaving `ww.cx` on its existing Namecheap Private Email path during the initial rollout.

## Verified source state

- Repository: `johnkaminski727-alt/edge1-management-interface`.
- Current GitHub `main` included Cookie Monster Alpha foundation at `66397434b7d89629682dd9ca459aaf8607a0d575` when this branch was created.
- Existing Mail Room provider inventory records:
  - `ww.cx` on Namecheap Private Email;
  - `creekco.ca`, `scgardens.ca`, and `omegafx.com` on Namecheap shared-hosting MX;
  - `spiritcreekgardens.com` with no published MX in the 2026-08-20 resolver observation.
- Existing Mail Room identity/routing configuration already contains Creekco, Spirit Creek Gardens, and Omegafx logical addresses.
- A real Namecheap `blank@ww.cx` -> Mail Room `production_native` ingestion acceptance was completed before this gateway project.

## Durable decisions

1. `mail.ww.cx` is the stable service hostname.
2. Do not use a `test` hostname for the gateway.
3. `ww.cx` remains external in v1; preserve Namecheap Private Email and the existing connector.
4. Preserve `domaincontact@ww.cx` as a distinct domain-authority identity.
5. Edge1 catch-all migration order: Creekco, Spirit Creek Gardens, scgardens.ca if needed, then Omegafx.
6. One domain migrates at a time.
7. Original recipient preservation is mandatory.
8. Catch-all receive authority never grants send authority.
9. Provider/cPanel adapters stay available for rollback/migration.
10. DNS, firewall, certificates, public SMTP listener activation, provider cancellation, and outbound mail remain explicit approval boundaries.

## Repository changes on branch

- `docs/messaging-operations/edge1-mail-gateway-v1-20260822.md`
- `schemas/messaging/edge1-mail-gateway-v1.schema.json`
- `config/messaging/edge1-mail-gateway-v1.json`
- `tests/validate_edge1_mail_gateway_v1.py`
- `.github/workflows/edge1-mail-gateway-v1.yml`

All configuration is disabled by default.

## Next safe engineering work

1. Validate branch CI and repository-wide compatibility.
2. Add local-only MTA configuration templates for managed virtual domains with public binding disabled.
3. Add relay-denial and catch-all/original-recipient tests.
4. Add local Mail Room source normalization from the Edge1 mail store.
5. Add backup/rollback and acceptance tooling.
6. Prepare, but do not apply, `mail.ww.cx` DNS/certificate/firewall change sets.
7. Obtain explicit authorization before public SMTP listener/DNS activation.

## Live-state caution

The bounded Edge1 operator currently reports a detached repository HEAD at `d326d4546abefa695a293266342a5c1075f010e2`, which does not match current GitHub `main`. Do not deploy from that operator view without first reconciling the actual live checkout/branch state through an authenticated operator session.
