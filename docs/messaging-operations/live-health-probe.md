# Messaging Gateway Live Health Probe

The messaging operations collector reports live, read-only loopback health rather than the static Phase 1 degraded baseline.

Verified Edge1 runtime endpoints:

- `http://127.0.0.1:58080/healthz` returns HTTP 200 with `{"status":"ok"}`.
- `http://127.0.0.1:58080/readyz` returns HTTP 200 with `{"status":"ready","storage":"memory"}`.

The collector also performs `systemctl is-active --quiet wwcx-messaging-gateway.service` as a read-only service-state check.

## Safety boundary

The probe:

- connects only to `127.0.0.1`;
- performs HTTP GET requests only;
- applies short timeouts;
- sends no credentials;
- performs no service restart or configuration write;
- performs no PBX, routing, carrier, SMS, or MMS action.

A snapshot is `healthy` only when the service is active and both loopback health endpoints return their expected healthy states. All production messaging actions remain disabled regardless of health state.
