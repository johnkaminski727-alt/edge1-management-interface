# Telephony Analytics API

## Purpose

`server/telephony_analytics_api.py` exposes privacy-minimized aggregate telephony health, call, interconnect, and anomaly-indicator views for the loopback-only Big Bird telephony console and approved internal tooling.

The service is intentionally read-only and contains no production-changing control path.

## Listener boundary

Default listener:

```text
127.0.0.1:8099
```

The server accepts only loopback host values:

- `127.0.0.1`
- `::1`
- `localhost`

Binding to `0.0.0.0`, a public address, or a private network address is rejected by argument validation.

## Endpoints

Health probe:

```text
GET /healthz
```

Aggregate platform health:

```text
GET /api/telephony/platform/health
```

Aggregate call summary:

```text
GET /api/telephony/platform/calls/summary
```

Aggregate interconnect summary:

```text
GET /api/telephony/platform/interconnects/summary
```

Aggregate anomaly indicators:

```text
GET /api/telephony/platform/anomalies
```

The anomaly endpoint evaluates only the same accepted aggregate health, call, and interconnect dictionaries returned by the other endpoints. It emits exactly six fixed indicators with mode:

```text
informational_no_enforcement
```

The endpoint does not expose carrier identifiers, countries, SIP-code labels, failure-class labels, component detail, or source aggregate maps. It emits bounded derived values, fixed thresholds, fixed reason codes, fixed same-page investigation anchors, and safety flags that are all false.

Every non-GET write method is rejected with HTTP `405` and a `read_only` error.

## Privacy boundary

The API returns synthetic privacy-minimized fixtures until a separately reviewed live adapter is authorized and installed.

The aggregate payloads contain:

- normalized health state and score;
- aggregate call counts and durations;
- direction, disposition, sanitized carrier, country, SIP-code, and failure-class counts;
- aggregate interconnect states and latency;
- bounded aggregate anomaly values and sample sizes.

The anomaly payload deliberately omits the aggregate category labels used to calculate its derived ratios and concentrations.

The API must not return:

- calling or called telephone numbers;
- customer names or account numbers;
- SIP credentials or authorization headers;
- message bodies;
- media, recordings, or SDP;
- private endpoint addresses;
- carrier portal credentials;
- raw CDR rows;
- notification, enforcement, route-change, or service-control instructions.

## No notification or enforcement

The anomaly endpoint does not send email, SMS, webhook, page, alarm, or ticket events. It does not block or throttle traffic, quarantine a source, alter a route, change a carrier, restart a service, modify configuration, originate a call or message, transmit DTMF, or perform automatic remediation.

`watch` and `critical` are informational operator-attention states only. `insufficient_data` is used when the fixed sample gates are not met.

## Service unit

Repository unit:

```text
deploy/telephony/wwcx-telephony-analytics.service
```

The unit runs as `wwadmin`, binds only to loopback, and uses systemd hardening controls including:

- `NoNewPrivileges=yes`
- `ProtectSystem=strict`
- `ProtectHome=yes`
- `PrivateTmp=yes`
- `MemoryDenyWriteExecute=yes`

The API reads no credential file and queries no database.

## Repository validation

From the repository root:

```bash
python3 tests/validate_telephony_anomaly_indicators.py
python3 tests/validate_telephony_analytics_api.py
```

Print the synthetic aggregate contract without opening a listener:

```bash
python3 server/telephony_analytics_api.py --print-sample
```

The sample output is safe for repository validation because it contains only synthetic data and false no-action safety flags.

## Manual local preview

Run only on an approved local development host:

```bash
python3 server/telephony_analytics_api.py \
  --host 127.0.0.1 \
  --port 8099
```

Read-only checks:

```bash
curl -fsS http://127.0.0.1:8099/healthz
curl -fsS http://127.0.0.1:8099/api/telephony/platform/health
curl -fsS http://127.0.0.1:8099/api/telephony/platform/calls/summary
curl -fsS http://127.0.0.1:8099/api/telephony/platform/interconnects/summary
curl -fsS http://127.0.0.1:8099/api/telephony/platform/anomalies
```

Method-boundary check:

```bash
curl -sS -o /dev/null -w '%{http_code}\n' \
  -X POST \
  http://127.0.0.1:8099/api/telephony/platform/anomalies
```

Expected result:

```text
405
```

## No runtime deployment in this increment

Adding the anomaly endpoint to the repository does not deploy it to the currently running analytics service. The previously accepted service may continue to execute an older worktree and therefore may return `404` for the new route until a separate bounded deployment is authorized.

This increment does not install, reload, restart, or replace the analytics service. It does not change a listener, firewall, DNS, certificate, route, carrier, PBX, database, credential, call, message, or DTMF path.

A future deployment must:

1. verify a clean accepted repository revision;
2. confirm the current service source and rollback path;
3. update the service source using the documented deployment procedure;
4. keep the listener on `127.0.0.1:8099`;
5. verify all four aggregate GET endpoints and write-method rejection;
6. verify anomaly safety flags and privacy omissions;
7. verify repository index ownership remains unchanged;
8. capture protected evidence;
9. roll back if any existing endpoint or listener boundary changes unexpectedly.

## Acceptance boundary

Repository validation proves only that the bounded read-only implementation and synthetic contract are internally consistent.

It does not prove:

- live source integration;
- report correctness or source completeness;
- production route readiness;
- carrier interoperability;
- fraud or root-cause diagnosis;
- emergency-calling readiness;
- regulatory status;
- runtime deployment of the anomaly route;
- authorization for notification or enforcement.
