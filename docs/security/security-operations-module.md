# WW.CX Security Operations Module

## Purpose

The Security Operations module provides human-readable visibility into the managed Edge1 Suricata deployment and a controlled path toward safe browser-based operations.

The module is designed around:

Observe -> Understand -> Validate -> Evidence -> Controlled Action

## Components

### Managed Suricata sensor

Service:

- `wwcx-network-sensor-suricata.service`

Capture source:

- explicit libpcap capture on `wg0` for the authorized addressed-interface deployment;
- full PCAP recording remains a separate service under `wwcx-network-sensor-pcap.service`.

Observed data:

- service state;
- version;
- memory usage;
- EVE telemetry;
- current packet counters;
- recent alerts.

The former Project Big Bird `suricata.service` duplicate is retired and disabled. Project Big Bird consumes the managed sensor feed instead of running a second detection engine.

### Collector

Authoritative source:

- `server/bigbird_ops_collect.py`

Runtime installation:

- `/usr/local/libexec/bigbird-ops-collect.py`

Publisher service and timer:

- `bigbird-ops-push.service`;
- `bigbird-ops-push.timer`.

Publishes security telemetry into:

- `/var/lib/bigbird/operations-center/latest.json`.

The source collector publishes the bounded alert schema `wwcx.suricata-source-alert.v1`. It retains only allowlisted alert metadata required for investigation and excludes packet payloads, raw EVE events, credentials, private keys, original nested alert objects, and arbitrary metadata.

The managed source identity is:

- service: `wwcx-network-sensor-suricata.service`;
- EVE path: `/var/log/wwcx-network-sensor/suricata/eve.json`;
- source release: `edge1-suricata-sensor-consolidation-r1`.

The older copy under the archived WW.CX Project Big Bird V4.0.7 release package is historical release evidence and is not the editable Edge1 source.

### Exporter

Path:

- `server/security_operations_exporter.py`

Publishes:

- `/var/www/edge1-status/security-operations.json`.

The exporter converts the source collector contract into Security Operations schema `2.0` and alert schema `wwcx.suricata-alert.v1`, applies the public 50-alert bound, and provides last-known-good fallback metadata.

### Live read-only dashboard

Path:

- `src/web/security/index.html`

Live route:

- `/edge1-status/security/`

Provides:

- engine status;
- health state;
- alert explanations;
- accessible alert drill-down;
- validation evidence;
- configuration advisories;
- live versus stale-cache status.

This page is an observation and investigation surface. It does not submit live service changes.

### Human operator console foundation

Prototype path:

- `src/web/edge1-ops/security/index.html`

Policy:

- `config/security/edge1-security-operator-console.json`

Planned restricted route:

- `/edge1-ops/security/`

The prototype presents service health and maintenance actions in ordinary language. It explains expected effects, confirmations, results, evidence, and recovery guidance. Production action buttons remain locked until the authenticated browser boundary and server-side action gateway are implemented and accepted.

The browser must never receive the loopback Operations API signing secret or construct HMAC requests directly.

## Controlled actions

Registered operations:

- `security.validate_config`;
- `security.logs.rotate`;
- `security.rules.reload`.

Current policy:

- machine-client configuration validation is allowlisted;
- browser actions are disabled;
- browser mutations are disabled;
- production authentication and route activation are not authorized.

The existing loopback Operations API is controlled by:

- `EDGE1_OPS_MUTATIONS_ENABLED`.

A future browser gateway will enforce separate browser authentication, CSRF protection, per-action authorization, typed confirmations for mutations, rate limits, and append-only audit before translating an approved request into an allowlisted machine action.

## Evidence

Security action evidence location:

- `/var/lib/edge1-operations-api/evidence/security`.

Collector enrichment deployment evidence:

- `/var/lib/wwcx-deployment-evidence/suricata-collector-enrichment/<timestamp>`.

Managed sensor deployment evidence:

- `/var/lib/wwcx-deployment-evidence/network-sensor/<timestamp>`.

Suricata runtime consolidation evidence:

- `/var/lib/wwcx-deployment-evidence/suricata-runtime-consolidation/<timestamp>`.

## Current validation

Validated:

- the managed Suricata service is active and enabled;
- libpcap capture on `wg0` produces nonzero fresh counters;
- telemetry is available;
- the duplicate legacy service is inactive and disabled;
- the Project Big Bird collector uses the managed EVE source;
- the exporter is functioning;
- the live read-only dashboard data is available;
- alert expand and collapse behavior is functioning;
- last-known-good cache behavior is functioning;
- nested alert classification and risk normalization are functioning;
- Network Defense reports the sensor as observed without changing traffic controls.

## Advisory handling

Expected runtime selection is informational:

- explicitly authorized addressed interfaces such as `wg0` use `--pcap=wg0`;
- normal unaddressed mirror or TAP deployments retain AF_PACKET as the default;
- Zeek remains disabled for the accepted Suricata and PCAP baseline.

## Operator-console roadmap

See:

- `docs/security/edge1-security-operator-console-roadmap-20260805.md`.

The next safe repository phase is a provider-neutral server-side browser gateway behind a denied-by-default staging route. Production authentication, Apache route activation, and live browser mutations remain separate explicit approval boundaries.
