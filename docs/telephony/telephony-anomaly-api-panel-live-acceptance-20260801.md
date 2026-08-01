# Telephony Anomaly API and Console Panel Live Acceptance — 2026-08-01

## Decision

**Accepted for private, loopback-only, read-only operational use on Edge1.**

The corrected bounded deployment completed successfully on `edge1.ww.cx` at 2026-08-01 21:50 UTC. The canonical console process was refreshed once, the analytics service was moved from the prior accepted worktree to canonical `main`, and the complete read-only live-acceptance audit passed with zero warnings and zero failures.

This acceptance does not authorize live CDR, AMI/ARI, SIP-edge, log, packet, carrier, or database collectors; public exposure; authentication changes; notifications; traffic enforcement; call or message origination; DTMF transmission; routing changes; emergency-calling tests; number-porting actions; or carrier administration.

## Accepted repository state

```text
repository: johnkaminski727-alt/edge1-management-interface
host checkout: /opt/edge1-management-interface
branch: main
accepted repository head: cd17fc882eb2714fb7ec64c920d561628f7848f7
corrective deployment merge: cd17fc882eb2714fb7ec64c920d561628f7848f7
repository state after deployment: clean
Git index owner: wwadmin:wwadmin
Git index mode: 0600
```

## Runtime state

### Private console

```text
service: wwcx-telephony-console.service
state: active/running
runtime source: /opt/edge1-management-interface/server/telephony_status_server.py
working directory: /opt/edge1-management-interface
user/group: wwadmin:wwadmin
listener: 127.0.0.1:8096
accepted PID during deployment: 2179081
restart performed: one bounded canonical-process refresh
```

The same-origin route changed from HTTP `404` before the refresh to HTTP `200` after the refresh:

```text
/api/telephony/analytics/health
```

The returned body parsed as valid JSON and carried the accepted anomaly contract.

### Aggregate analytics

```text
service: wwcx-telephony-analytics.service
state: active/running and enabled
runtime source: /opt/edge1-management-interface/server/telephony_analytics_api.py
working directory: /opt/edge1-management-interface
user/group: wwadmin:wwadmin
listener: 127.0.0.1:8099
accepted PID during deployment: 2179320
restart performed: one bounded deployment restart
```

The prior analytics unit and worktree were captured before mutation. The successful deployment did not require rollback.

## Source provenance

The live audit resolved and compared the three runtime modules against canonical repository files:

```text
/opt/edge1-management-interface/server/telephony_analytics_api.py
/opt/edge1-management-interface/server/telephony_platform.py
/opt/edge1-management-interface/server/telephony_anomaly_indicators.py
```

Accepted results:

```text
runtime_api_source_match=yes
runtime_platform_source_match=yes
runtime_anomaly_source_match=yes
```

## Functional and safety validation

Repository validation passed immediately before deployment:

```text
telephony anomaly indicator validation passed
telephony analytics API validation passed
telephony analytics console panel validation passed
telephony anomaly API and console panel validation passed
telephony anomaly live deployment validation passed
```

The read-only live audit accepted:

- analytics and console services active;
- analytics enabled at boot;
- canonical runtime source provenance for API, platform, and anomaly modules;
- loopback-only listeners on ports `8096` and `8099`;
- valid health, platform-health, anomaly, call-summary, and interconnect-summary JSON;
- dedicated and nested anomaly contracts;
- same-origin console anomaly delivery;
- POST rejection with HTTP `405`;
- payload privacy validation;
- fixed informational/no-enforcement anomaly mode;
- unchanged `wwadmin:wwadmin` Git-index ownership;
- clean repository state.

Final audit result:

```text
warnings=0
failures=0
payload_validation=passed
privacy_scan=passed
anomaly_contract=passed
console_anomaly_contract=passed
telephony_anomaly_api_panel_live_acceptance=passed
anomaly_live_deployment=passed
rollback_required=no
```

## Protected evidence

Top-level corrected deployment evidence:

```text
/var/lib/wwcx-deployment-evidence/telephony-anomaly-api-panel-deployment/20260801T214954Z
```

Top-level deployment manifest SHA-256:

```text
a96ce9e6fbcf021d9a21ccfd163f5b89d5408840d495a468f265ee1db2849b2a
```

Console-refresh evidence:

```text
/var/lib/wwcx-deployment-evidence/telephony-anomaly-api-panel-deployment/20260801T214954Z/console-refresh
```

Analytics-deployment evidence:

```text
/var/lib/wwcx-deployment-evidence/telephony-anomaly-api-panel-deployment/20260801T214954Z/analytics-deployment
```

Analytics-deployment manifest SHA-256:

```text
9a16816c21324b4f0ad9f072ca05ec8f92fdd64620f176bc03955b9cd3573be5
```

Read-only live-acceptance evidence:

```text
/var/lib/wwcx-deployment-evidence/telephony-anomaly-api-panel-live-acceptance/20260801T215006Z
```

Live-acceptance manifest SHA-256:

```text
103befc105fa0bd2684125930d534860e92cca6efc6f30fe0051c5c153e42c43
```

## Historical failed attempt and rollback

The earlier deployment attempt at 2026-08-01 21:29 UTC correctly failed because the long-running console process still held an older in-memory route map and returned HTTP `404` for the same-origin health route. The deployment engine automatically restored the exact prior analytics unit and restarted its former accepted worktree. Both services remained active and loopback-only, and the repository remained clean.

That failure led to the corrected v2 sequence: refresh and prove the canonical console process first, then execute the existing rollback-capable analytics deployment.

## Explicitly unverified or unauthorized

This acceptance does not prove or authorize:

- production CDR or SIP-event ingestion;
- AMI, ARI, database, log, packet, or carrier-source access;
- carrier or end-to-end interoperability;
- production call, message, or DTMF behavior;
- routing, trunk, endpoint, dial-plan, registration, or DID changes;
- emergency-calling readiness;
- NPAS certification, EAS compliance, Alert Ready compliance, STIR/SHAKEN signing, or regulatory approval;
- automated notification, fraud blocking, traffic enforcement, rerouting, or remediation;
- public listener, firewall, DNS, certificate, or authentication changes.

The accepted anomaly surface remains informational, aggregate-only, private, loopback-bound, and read-only.
