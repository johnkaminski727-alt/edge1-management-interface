# Outbound Mail Phase B2 Readiness State

Last reconciled: 2026-08-01 20:48 UTC  
Repository: `johnkaminski727-alt/edge1-management-interface`  
Parameter discovery issue: #233  
Parent activation issue: #187

## Verified prerequisite

Phase B1 is accepted live on `edge1.ww.cx`:

- service `wwcx-outbound-mail-gateway.service` is active and enabled;
- listener remains restricted to `127.0.0.1:8104`;
- preparation authentication is enabled with a root-owned runtime credential;
- `/outbound-mail/healthz` returns HTTP `200`;
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
- unsigned preparation API: HTTP `401`;
- send probe: HTTP `403`.

The audit completed without reading HMAC or certificate private-key contents and without changing runtime or network state.

## Historical baseline authorization record

At the time of that baseline:

- certificate/private-key content access authorized: **no**;
- proxy installation or reload authorized: **no**;
- DNS change authorized: **no**;
- firewall change authorized: **no**;
- production message authorized: **no**.

A generic `Continue` does not authorize those privileged actions. This historical statement remains preserved even though later authorization expanded the bounded project scope.

## Later authorization received

At approximately 2026-08-01 19:40 UTC, after the remaining B2/C work and privileged boundaries were stated, the user wrote: `I am authorizing all work.`

This authorizes bounded production configuration only after exact parameters, reviewed code, validation, rollback, and evidence requirements are satisfied. It does not authorize secret disclosure, destructive or irreversible work, financial or legal commitments, or an unspecified production message or recipient.

## Accepted live parameter discovery

### First run and remediation

The first run at `2026-08-01T20:08:56Z` correctly identified Apache and the active certificate references but was marked not ready because the initial script probed `/healthz` rather than `/outbound-mail/healthz`. PR #243 merged the corrected health route and active-vhost selection as commit `672461ce0f996871be7613a5d6c16bf4950e986d`.

### Corrected run

The corrected discovery was executed through authenticated SSH by `wwadmin`; the audit ran as `root`.

Accepted facts:

- captured at: `2026-08-01T20:41:48Z`;
- audited repository HEAD: `b5614ffc7ff309b50c8b799e155d41cf67433811`;
- evidence: `/var/lib/wwcx-deployment-evidence/outbound-mail-phase-b2-parameter-discovery/20260801T204148Z`;
- hostname: `edge1.ww.cx`;
- exact business159 source: `162.0.217.71/32`;
- health: HTTP `200`;
- unsigned preparation: HTTP `401`;
- send probe: HTTP `403`;
- active `edge1.ww.cx` vhost blocks: `2`;
- approved full-chain references in the enabled site: `1`;
- approved private-key references in the enabled site: `1`;
- active TLS pair in the enabled site: yes;
- full-chain path: `/etc/letsencrypt/live/edge1.ww.cx/fullchain.pem`;
- private-key path: `/etc/letsencrypt/live/edge1.ww.cx/privkey.pem`;
- readiness: `ready_for_phase_b2_proposal_validation`;
- failures: `0`;
- pending decisions: `0`;
- SHA-256 evidence manifest: passed.

The two vhost blocks are expected because the enabled site contains non-TLS and TLS blocks for the same hostname. They are not certificate ambiguity.

## Current exact proposal inputs

```text
PROPOSED_HOSTNAME=edge1.ww.cx
PROPOSED_CLIENT_CIDR=162.0.217.71/32
CERTIFICATE_FULLCHAIN_PATH=/etc/letsencrypt/live/edge1.ww.cx/fullchain.pem
CERTIFICATE_PRIVATE_KEY_PATH=/etc/letsencrypt/live/edge1.ww.cx/privkey.pem
ACTIVE_VHOST=/etc/apache2/sites-enabled/edge1.ww.cx.conf
```

## Apache-specific proposal package

Live discovery proves Apache 2, not nginx, owns port 443. The next repository package therefore:

- renders an Apache include fragment rather than an nginx server block;
- validates the exact enabled `edge1.ww.cx` vhost;
- accepts the standard Let's Encrypt `live` symlinks only when they resolve under `/etc/letsencrypt/archive/edge1.ww.cx/`;
- inspects public certificate metadata but does not read private-key contents;
- exposes exactly the status and prepare routes in the evidence-only candidate;
- restricts both routes to `162.0.217.71/32`;
- retains continued send denial and disabled external delivery.

The expected proposal state is `ready_for_explicit_b2_apache_authorization`.

## Current authorization and execution state

- B2 baseline audit execution: **accepted**;
- B2 parameter discovery package: **merged and executed**;
- corrected discovery evidence: **accepted**;
- Apache-specific proposal package: **in repository review**;
- exact B2 hostname: **`edge1.ww.cx`**;
- exact client source: **`162.0.217.71/32`**;
- active proxy service: **Apache 2**;
- active certificate paths: **identified by enabled-vhost references and pathname metadata**;
- certificate/private-key content disclosure: **prohibited**;
- proxy installation or reload: **not yet executed**;
- DNS change: **not currently indicated**;
- firewall change: **not currently indicated**;
- public preparation route: **not yet activated**;
- website bridge deployment/activation: **not yet activated**;
- provider, sender, or delivery activation: **not yet configured**;
- production message: **not defined or sent**.

## Verified non-mutation markers

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

Merge and run the Apache-specific proposal audit. Require `ready_for_explicit_b2_apache_authorization` and a valid evidence manifest before reviewing a rollback-capable Apache installer. No live route, reload, website bridge, provider, sender, delivery, or message action may precede that acceptance.
