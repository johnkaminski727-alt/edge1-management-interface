# Outbound Mail Phase B2 Readiness State

Last reconciled: 2026-08-01 19:48 UTC  
Repository: `johnkaminski727-alt/edge1-management-interface`  
Parameter discovery issue: #233  
Parent activation issue: #187

## Verified prerequisite

Phase B1 is accepted live on `edge1.ww.cx` and remained accepted during the B2 baseline audit:

- service `wwcx-outbound-mail-gateway.service` remains on loopback `127.0.0.1:8104`;
- preparation authentication remains enabled with a root-owned runtime credential;
- unsigned preparation requests return HTTP `401`;
- send returns HTTP `403`;
- external delivery and policy remain disabled;
- live sender count remains zero;
- ready provider count remains zero.

## Accepted Phase B2 baseline audit

The read-only baseline audit was executed through authenticated SSH by `wwadmin`; the audit itself ran as `root` through `sudo`.

Accepted facts:

- audit timestamp: `2026-08-01T19:28:18Z`;
- host: `edge1.ww.cx`;
- branch: `main`;
- audited repository HEAD: `03f8a67b17b258459ee71b6a2a7a31187987506c`;
- B1 live-acceptance commit: `53bb0ea15cdedb136add858841813273252cc8fc`;
- B2 template baseline: `f1f65571902c7f377c6a7ca9c52f634973a7635a`;
- readiness state: `awaiting_explicit_b2_parameters`;
- evidence directory: `/var/lib/wwcx-deployment-evidence/outbound-mail-phase-b2-readiness/20260801T192818Z`;
- proposed hostname: not supplied in that run;
- proposed client CIDR: not supplied;
- certificate full-chain path: not supplied;
- certificate private-key path: not supplied;
- unsigned preparation API: HTTP `401`;
- send probe: HTTP `403`.

The audit completed without reading HMAC or certificate private-key contents and without changing runtime or network state.

## Historical baseline authorization record

At the time the baseline audit was accepted:

- certificate/private-key content access authorized: **no**;
- proxy installation or reload authorized: **no**;
- DNS change authorized: **no**;
- firewall change authorized: **no**;
- production message authorized: **no**.

A generic `Continue` does not authorize those privileged actions. This historical statement describes the accepted baseline at 19:28 UTC and is preserved unchanged even though later authorization expanded the project scope.

## Authorization received

At approximately 2026-08-01 19:40 UTC, after the remaining B2/C work and privileged boundaries were stated, the user wrote: `I am authorizing all work.`

This is accepted as authorization to continue the outbound-mail project end to end, including bounded production configuration work after exact parameters, validation, rollback, and evidence requirements are satisfied. It does not waive credential secrecy, authorize disclosure or transmission of private-key/HMAC contents, permit destructive or irreversible work without a verified rollback, accept financial/legal terms, or define an unspecified production message or recipient.

## Parameter discovery in progress

The committed website bridge fixes the exact API hostname as:

```text
edge1.ww.cx
```

The bridge rejects alternate hosts, ports, paths, queries, fragments, credentials, and redirects.

The remaining proposal inputs must be evidenced rather than guessed:

1. actual business159 outbound NAT address as one `/32` or `/128`;
2. existing approved certificate full-chain path on Edge1;
3. corresponding existing private-key path identified by metadata only;
4. selected active reverse-proxy service and destination configuration path.

Issue #233 tracks a read-only Edge1 discovery tool. Website issue `johnkaminski727-alt/ww-cx-website#36` tracks the business159 egress measurement. An A or AAAA record is not accepted as proof of outbound NAT identity.

## Current authorization and execution state

- B2 baseline audit execution: **accepted**;
- B2 parameter discovery package: **authorized and in repository review**;
- exact B2 hostname: **`edge1.ww.cx`, fixed by committed bridge contract**;
- exact client source `/32` or `/128`: **not yet measured**;
- certificate paths: **not yet discovered and accepted**;
- certificate/private-key content disclosure: **prohibited**;
- proxy installation or reload: **authorized only after exact proposal validation and rollback review**;
- DNS change: **authorized only if proposal evidence proves it is required and the exact record is recorded**;
- firewall change: **authorized only if proposal evidence proves it is required and the exact rule is recorded**;
- public listener or route: **not yet activated**;
- external signed canary: **authorized only after the restricted proxy is installed and source allow-list is verified**;
- website bridge deployment/activation: **authorized only after B2 external canary acceptance and secure shared-secret installation**;
- provider, sender, or delivery activation: **not yet configured**;
- production message: **not defined or sent**.

## Verified non-mutation markers from the accepted baseline

- `hmac_secret_read=no`;
- `certificate_private_key_read=no`;
- `candidate_config_written_to_evidence_only=yes`;
- `proxy_config_installed=no`;
- `proxy_service_reloaded=no`;
- `certificate_generated=no`;
- `dns_modified=no`;
- `firewall_modified=no`;
- `public_listener_added=no`;
- `website_bridge_enabled=no`;
- `provider_or_sender_enabled=no`;
- `message_sent=no`.

## Next execution gate

Run both read-only parameter discovery tools and accept their evidence. Then run the existing Phase B2 proposal-validation audit with all four exact values. Live proxy installation follows only if that proposal reaches `ready_for_explicit_b2_authorization` and the installation package preserves rollback, source restriction, exact-route exposure, HMAC authentication, and continued send denial.
