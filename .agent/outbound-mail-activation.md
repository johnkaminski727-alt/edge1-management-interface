# Outbound Mail Activation State

Last reconciled: 2026-08-01 09:04 UTC  
Repository: `johnkaminski727-alt/edge1-management-interface`  
Authoritative branch: `main`

## Verified live Phase A baseline

Authenticated Edge1 operator evidence recorded the disabled outbound-mail foundation as successfully deployed on `edge1.ww.cx` at 2026-08-01 06:47 UTC.

Verified facts:

- deployed repository HEAD: `31c96d4cf7b088bffd86e9a42b307da094181b0c`;
- approved Phase A readiness implementation `a4f6925902d778a450c1e54b2fcf2ab43286f119` was an ancestor and its protected files were unchanged;
- service: `wwcx-outbound-mail-gateway.service`;
- service principal: `wwcx-mail-gateway`;
- unit state: loaded, enabled, active/running;
- listener: loopback `127.0.0.1:8104`;
- evidence directory: `/var/lib/wwcx-deployment-evidence/outbound-mail-phase-a/20260801T064714Z`;
- health and status endpoints returned HTTP 200;
- unsigned preparation API status returned HTTP 403;
- send probe returned HTTP 403;
- external delivery, policy activation, preparation API, providers, and every live sender remained disabled;
- no runtime HMAC secret was configured;
- hidden open tracking and device fingerprinting remained disabled;
- message bodies and attachment bytes were not persisted.

Phase A is accepted as a disabled-only live foundation.

## Completed Phase B repository package

PR #200 merged as `c55059c2d0230ea273709bbb5a4169b00bb226c1`.

The package separates:

- **B1:** loopback-only HMAC preparation activation with root-owned runtime material, clean-main and exact-package checks, signed `prepared_not_sent` canary, replay rejection, no-send verification, rollback, and restricted evidence;
- **B2:** a separately authorized TLS reverse-proxy boundary exposing only authenticated status and preparation routes.

Repository and Edge1 Operator CI passed. The real gateway was tested with temporary CI-only material. Authentication, replay rejection, canonical sender selection, audit redaction, and delivery denial passed.

## Current activation state

- Phase A live: **yes**;
- Phase B repository package merged: **yes**;
- B1 runtime overlay installed: **no**;
- production HMAC secret generated: **no**;
- production HMAC secret installed: **no**;
- B2 certificate or reverse proxy installed: **no**;
- DNS or firewall changed: **no**;
- website bridge activated: **no**;
- public correspondence route activated: **no**;
- retention apply or scheduling activated: **no**;
- provider credentials installed: **no**;
- sender identity activated: **no**;
- production mail delivery: **no**.

## Read-only readiness gate

`tools/messaging/outbound_mail_phase_b1_readiness_audit.sh` measures whether the live Phase A service is ready for explicit B1 authorization without generating or reading secret material and without modifying runtime state.

The audit checks:

- exact host and root execution;
- clean `main` repository state;
- Phase B package ancestry and unchanged protected files;
- committed disabled-state configuration;
- active/enabled service and expected service principal;
- loopback-only port 8104 listener;
- health/status success;
- preparation and send denial;
- absent B1 runtime overlay files;
- absence of a configured preparation API proxy path;
- restricted evidence and SHA-256 inventory.

This audit was prepared in the repository but was **not executed in this session** because no authenticated Edge1 shell was available.

A passing audit means **ready for explicit B1 authorization**. It does not authorize secret generation, authentication activation, proxy exposure, or mail traffic.

## Explicit approval boundary

The next privileged step requires exact user authorization for production secret generation and B1 installation. The authorization should be materially equivalent to:

> Authorize generation of a new production HMAC secret on Edge1 and installation of Phase B1 loopback preparation authentication only. Do not install B2, a certificate, DNS or firewall changes, the website bridge, public records, retention, provider credentials, sender activation, or mail delivery.

Until that authorization is given, permitted work is limited to read-only live inspection, documentation, CI, and reversible repository changes that do not create or install credentials.

## Stop conditions

Stop before:

- generating, displaying, transmitting, rotating, or installing secret material;
- installing the B1 runtime overlay;
- restarting the production service for B1 activation;
- installing B2 proxy or certificate configuration;
- changing DNS, firewall, authentication, or public routes;
- activating the website bridge, public record, retention apply, provider, sender, or mail delivery;
- sending any production message.
