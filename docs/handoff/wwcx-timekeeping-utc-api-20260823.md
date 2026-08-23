# WW.CX Timekeeping UTC API — 2026-08-23

## Status

Deployed live on `edge1.ww.cx` for the WW.CX Admin Account Settings **Time & Region** panel.

## Purpose

Provide a minimal, read-only UTC clock endpoint that lets WW.CX Admin display coordinated GMT/UTC time without trusting the workstation clock. The endpoint intentionally exposes no timekeeping records, credentials, MCP methods, or detailed NTP measurements.

## Runtime

- service: `wwcx-timekeeping-mcp.service`
- listener: `127.0.0.1:8092`
- live source: `/opt/wwcx-timekeeping-mcp/src/server.mjs`
- public route: `GET https://edge1.ww.cx/api/timekeeping/utc`
- transport: HTTPS through the existing Edge1 Apache vhost
- cache policy: `no-store`
- browser origin allowed for the Admin clock: `https://ww.cx`

The live timekeeping service reports version `0.1.2` after the UTC endpoint addition.

## Response contract

The endpoint returns only a sanitized status object:

```json
{
  "ok": true,
  "service": "wwcx-timekeeping",
  "version": "0.1.2",
  "timescale": "UTC",
  "utc": "2026-08-23T21:43:16.400Z",
  "unix_ms": 1787521396400,
  "source": "edge1-system-clock",
  "time_authority": {
    "ok": true,
    "reachable_sources": 5,
    "total_sources": 5,
    "expectations_met": 5,
    "generated_at_utc": "2026-08-23T21:43:16Z"
  }
}
```

The `time_authority` object is best-effort. If the private Time Authority summary is unavailable, the clock remains usable and the field is `null`.

## Time source boundary

The current UTC value is taken from the Edge1 system clock through the WW.CX Timekeeping service. Edge1 continues to use its existing host synchronization service; the separate WW.CX Time Authority remains a read-only observer and does not set the host clock.

Time Authority health is sampled from its localhost-only API on `127.0.0.1:8101`. Only aggregate counts are copied into the public clock response. Individual NTP source addresses, offsets, RTTs, and measurement history remain private.

## Validation

Verified live after deployment:

- `wwcx-timekeeping-mcp.service` active;
- `GET http://127.0.0.1:8092/utc` returns valid JSON;
- `GET https://edge1.ww.cx/api/timekeeping/utc` returns HTTP 200;
- response includes `Cache-Control: no-store`;
- response includes `Access-Control-Allow-Origin: https://ww.cx`;
- Business159 can reach the public endpoint;
- sanitized Time Authority status reported 5/5 reachable sources and 5 expectations met during validation.

## Safety

This endpoint does not change the host clock, NTP configuration, firewall, DNS, WireGuard, routing, timekeeping records, or MCP authorization. It is a read-only presentation endpoint for coordinated time and aggregate synchronization health.
