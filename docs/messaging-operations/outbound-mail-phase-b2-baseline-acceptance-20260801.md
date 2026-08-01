# Outbound Mail Phase B2 Baseline Acceptance — 2026-08-01

## Decision

The read-only Phase B2 baseline audit is **accepted** for inventory and prerequisite tracking only.

This acceptance does not authorize certificate access, certificate issuance, reverse-proxy installation or reload, DNS or firewall changes, public exposure, external canaries, website bridge activation, provider or sender activation, delivery enablement, retention changes, or message traffic.

## Authenticated execution

- SSH principal: `wwadmin`;
- audit principal: `root` through `sudo`;
- host: `edge1.ww.cx`;
- repository: `/opt/edge1-management-interface`;
- branch: `main`;
- audited HEAD: `03f8a67b17b258459ee71b6a2a7a31187987506c`;
- captured at: `2026-08-01T19:28:18Z`.

## Protected evidence

```text
/var/lib/wwcx-deployment-evidence/outbound-mail-phase-b2-readiness/20260801T192818Z
```

The audit reported completion and identified no runtime or network mutation. The evidence manifest was not separately reproduced in the operator transcript, so this acceptance does not claim an independent `sha256sum -c` verification.

## Accepted runtime boundary

The audit verified the accepted B1 boundary remained in effect:

- unsigned preparation API status: HTTP `401`;
- send probe: HTTP `403`;
- gateway preparation remains authenticated and loopback-only;
- external delivery remains disabled;
- policy remains disabled;
- no ready provider or live sender was activated.

## Readiness result

```text
readiness_state=awaiting_explicit_b2_parameters
```

The following proposal inputs were intentionally absent:

- exact API hostname;
- exact client source `/32` or `/128`;
- certificate full-chain path;
- certificate private-key path.

The result means the current B1 state and B2 prerequisites were safely inventoried. It does not mean the proxy is ready for installation or that any production parameter has been approved.

## Non-mutation acceptance

The operator transcript recorded:

```text
hmac_secret_read=no
certificate_private_key_read=no
candidate_config_written_to_evidence_only=yes
proxy_config_installed=no
proxy_service_reloaded=no
certificate_generated=no
dns_modified=no
firewall_modified=no
public_listener_added=no
website_bridge_enabled=no
provider_or_sender_enabled=no
message_sent=no
```

No HMAC value, certificate private-key content, credential, message body, or provider secret was disclosed or committed.

## Required next decision

A proposal-validation run may occur only after all four exact proposal inputs are selected. Any live B2 activation requires a separate authorization that also names the reverse proxy, target configuration path, reload scope, DNS/firewall changes if any, external signed-canary source, rollback procedure, and evidence location.

A generic continuation instruction does not authorize those privileged actions.
