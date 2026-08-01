# WW.CX Outbound Mail Gateway Phase B1 Live Acceptance

Date: 2026-08-01  
Host: `edge1.ww.cx`  
Operator path: authenticated SSH as `wwadmin`, bounded activation through `sudo` as `root`  
Service: `wwcx-outbound-mail-gateway.service`

## Accepted scope

Phase B1 enables the authenticated outbound-mail preparation API on the Edge1 loopback listener. It does not enable a public route, a delivery provider, a live sender, policy enforcement, or external message delivery.

Approved activation baseline and deployed repository HEAD:

```text
f1f65571902c7f377c6a7ca9c52f634973a7635a
```

Live evidence directory:

```text
/var/lib/wwcx-deployment-evidence/outbound-mail-phase-b1/20260801T190027Z
```

## Activation result

The operator-run activation wrapper reported:

```text
Phase B1 loopback preparation authentication activated successfully.
B2 reverse proxy: not installed
External delivery: disabled
```

The final validation marker was:

```text
PHASE_B1_VALIDATION=PASS
```

## Verified runtime state

- service active: yes;
- service enabled: yes;
- service principal: `wwcx-mail-gateway`;
- listener: exactly `127.0.0.1:8104`;
- preparation API enabled: yes, loopback only;
- runtime HMAC credential configured: yes;
- gateway state: `disabled`;
- external delivery enabled: no;
- policy enabled: no;
- live sender count: zero;
- ready provider count: zero;
- unsigned preparation API response: HTTP `401`;
- send endpoint response: HTTP `403`.

## Runtime material

The operator verified metadata only; no credential value was displayed or copied into this record.

```text
/etc/wwcx/outbound-mail-gateway.env
  owner=root:root mode=0600

/etc/wwcx/outbound-mail-gateway.json
  owner=root:root mode=0644

/etc/systemd/system/wwcx-outbound-mail-gateway.service.d/20-preparation-api.conf
  owner=root:root mode=0644
```

The temporary source-token check returned:

```text
temporary_secret_sources=0
```

## Evidence integrity

Every file listed in the evidence manifest passed `sha256sum -c SHA256SUMS`, including:

- `canary.txt`;
- `health-after-restart.json`;
- `readiness-after-restart.txt`;
- `listeners-after.txt`;
- `runtime-config.json`;
- `runtime-sha256.txt`;
- service and status snapshots;
- the sanitized journal capture.

The successful installer path requires the signed preparation canary, replay rejection, and delivery denial to complete before it prints success. No message was sent.

## Prior failed attempt

The first authorized activation attempt at 2026-08-01 18:35 UTC failed because the canary ran before the Python listener became ready. Automatic rollback restored the Phase A disabled state and removed all runtime and temporary secret material. PR #214 added a bounded systemd-and-HTTP readiness wait. PR #215 added an explicit approved-baseline guard. The second attempt used both remediations and passed.

## Deferred boundaries

This acceptance does not authorize or establish any of the following:

- B2 reverse proxy or certificate installation;
- DNS, firewall, public-listener, or public-route changes;
- website bridge or public correspondence activation;
- retention apply or scheduling;
- delivery-provider credentials or selection;
- live sender activation;
- external mail delivery or production message sending.

Each deferred boundary requires separate explicit authorization and its own validation and rollback plan.
