# Outbound Mail Activation State

Last reconciled: 2026-08-01 18:06 UTC  
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

## Accepted Phase B1 readiness audit

The read-only readiness audit from PR #205 was executed through an authenticated SSH session on `edge1.ww.cx` by `wwadmin`, with the audit itself running as `root` through `sudo`.

Accepted live evidence:

- audit time: `2026-08-01T17:45:48Z`;
- repository branch: `main`;
- audited repository HEAD: `bf7c9186f416d69e20f289a68c7a45314baae6b8`;
- Phase B package commit: `c55059c2d0230ea273709bbb5a4169b00bb226c1`;
- readiness result: `ready_for_explicit_b1_authorization`;
- unsigned preparation API status: HTTP `403`;
- send probe: HTTP `403`;
- production secret generated or read: no;
- runtime files modified: no;
- service restarted: no;
- proxy, DNS, or firewall modified: no;
- message sent: no;
- evidence directory: `/var/lib/wwcx-deployment-evidence/outbound-mail-phase-b1-readiness/20260801T174548Z`.

The audit passed all required repository, committed-policy, service, listener, endpoint, runtime-overlay, proxy-reference, and evidence checks. It changed no runtime or network state.

## Phase B1 activation authorization

At 2026-08-01 18:06 UTC, the user instructed `Continue` immediately after being presented with the exact Phase B1 approval boundary. That instruction is accepted as authorization for the following bounded action only:

- generate a new production HMAC secret locally on Edge1 without displaying or transmitting it;
- install the root-owned Phase B1 runtime configuration, environment file, and systemd drop-in;
- restart `wwcx-outbound-mail-gateway.service`;
- validate signed status, `prepared_not_sent`, replay rejection, and continued delivery denial;
- preserve restricted evidence and automatically restore the prior Phase A state if activation fails.

The authorized execution wrapper is:

```text
deploy/messaging/activate-outbound-mail-phase-b1.sh
```

It requires the exact approved repository commit, revalidates the accepted readiness evidence, refuses pre-existing B1 runtime files or any preparation-API proxy reference, creates the source token only in root-owned `/run` tmpfs, and removes that source file on every exit path. The installed environment file remains root-owned mode `0600` as the runtime credential.

This authorization does **not** include B2, certificates, DNS, firewall, website bridge, public correspondence records, retention apply or scheduling, provider credentials, sender activation, or mail delivery.

## Current activation state

- Phase A live: **yes**;
- Phase B repository package merged: **yes**;
- B1 readiness audit executed and accepted: **yes**;
- B1 readiness state: **ready for explicit B1 authorization**;
- Phase B1 activation authorized: **yes**;
- Phase B1 activation executed: **no**;
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

## Active execution boundary

Phase B1 may now be executed only through the reviewed one-shot wrapper at the exact approved commit. The operator must stop and report rather than bypassing any preflight, evidence, loopback, credential-permission, canary, rollback, or no-send check.

## Remaining stop conditions

Stop before:

- displaying, transmitting, exporting, or committing the production secret;
- installing B2 proxy or certificate configuration;
- changing DNS, firewall, or public routes;
- activating the website bridge, public record, retention apply, provider, sender, or mail delivery;
- sending any production message.
