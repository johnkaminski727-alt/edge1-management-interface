# Outbound Mail Phase B2 Readiness State

Last reconciled: 2026-08-01 20:23 UTC  
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

## Live parameter discovery evidence

### Edge1 first run

- captured at: `2026-08-01T20:08:56Z`;
- audited HEAD: `880edfeb3b79941a1d8f50a5eb92b1efe985dc61`;
- evidence: `/var/lib/wwcx-deployment-evidence/outbound-mail-phase-b2-parameter-discovery/20260801T200856Z`;
- unsigned preparation: HTTP `401`;
- send probe: HTTP `403`;
- Apache: active and enabled on port `443`;
- gateway: active and enabled on `127.0.0.1:8104`;
- private-key contents read: no;
- HMAC secret read: no;
- proxy/config/certificate/DNS/firewall/listener/website/provider/sender/message mutation: none.

The run was marked `not_ready` only because the discovery script incorrectly probed `/healthz`, which returned the gateway's expected HTTP `404` not-found response. The actual route `/outbound-mail/healthz` returned HTTP `200` during follow-up verification.

The broad inventory counted both `cert.pem` and `fullchain.pem` for the same leaf certificate and counted private-key paths from every Apache vhost. The enabled `edge1.ww.cx` Apache vhost resolves the active pair unambiguously:

```text
/etc/letsencrypt/live/edge1.ww.cx/fullchain.pem
/etc/letsencrypt/live/edge1.ww.cx/privkey.pem
```

The full chain covered `edge1.ww.cx`, `pbx.ww.cx`, and `sip.ww.cx`, and was valid from July 19, 2026 through October 17, 2026 at discovery time. The private-key path was root-owned with mode `0600`; contents were not read.

### Business159

- captured at: `2026-08-01T20:09:23Z`;
- host: `business159.web-hosting.com`;
- principal: `wwcxjywl`;
- audited website HEAD: `6d65ba2833d7ac20fa962f5457dedc45f75a2c47`;
- evidence: `/home/wwcxjywl/shared/ww-cx-website/evidence/outbound-mail-client-discovery/20260801T200923Z`;
- successful egress services: `3`;
- unique egress addresses: `1`;
- measured address: `162.0.217.71`;
- exact proposed source: `162.0.217.71/32`;
- evidence manifest: SHA-256 verification passed;
- readiness: `ready_for_edge1_b2_proposal_validation`;
- configuration/secret/deployment/bridge/provider/sender/message mutation: none.

## Current exact proposal inputs

```text
PROPOSED_HOSTNAME=edge1.ww.cx
PROPOSED_CLIENT_CIDR=162.0.217.71/32
CERTIFICATE_FULLCHAIN_PATH=/etc/letsencrypt/live/edge1.ww.cx/fullchain.pem
CERTIFICATE_PRIVATE_KEY_PATH=/etc/letsencrypt/live/edge1.ww.cx/privkey.pem
```

## Current authorization and execution state

- B2 baseline audit execution: **accepted**;
- B2 parameter discovery package: **merged and executed**;
- discovery false-negative remediation: **in repository review**;
- exact B2 hostname: **`edge1.ww.cx`**;
- exact client source: **`162.0.217.71/32`**;
- active proxy service: **Apache 2**;
- active full-chain path: **identified**;
- active private-key path: **identified by pathname metadata only**;
- certificate/private-key content disclosure: **prohibited**;
- proxy installation or reload: **authorized only after exact proposal validation and rollback review**;
- DNS change: **not currently indicated**;
- firewall change: **not yet established as required**;
- public preparation route: **not yet activated**;
- website bridge deployment/activation: **not yet activated**;
- provider, sender, or delivery activation: **not yet configured**;
- production message: **not defined or sent**.

## Verified non-mutation markers from the accepted baseline and discovery

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

Merge the discovery remediation, rerun the Edge1 discovery with `PROPOSED_CLIENT_CIDR=162.0.217.71/32`, verify its SHA-256 evidence manifest, and require `ready_for_phase_b2_proposal_validation`. Then run the existing non-mutating Phase B2 proposal audit with all four exact values. Live Apache configuration follows only after that proposal passes and an exact backup, syntax check, graceful reload, source-restriction canary, and rollback procedure are captured.
