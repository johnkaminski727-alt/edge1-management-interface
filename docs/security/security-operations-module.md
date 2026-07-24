# WW.CX Security Operations Module

## Purpose

The Security Operations module provides read-only visibility into the
Edge1 Suricata IDS deployment.

The module is designed around:

Observe -> Understand -> Validate -> Evidence -> Controlled Action

## Components

### Suricata

Service:

- `suricata.service`

Observed data:

- service state
- version
- memory usage
- EVE telemetry
- recent alerts

### Collector

Path:

- `/usr/local/libexec/bigbird-ops-collect.py`

Publishes security telemetry into:

- `/var/lib/bigbird/operations-center/latest.json`

### Exporter

Path:

- `server/security_operations_exporter.py`

Publishes:

- `/var/www/edge1-status/security-operations.json`

### Dashboard

Path:

- `src/web/security/index.html`

Provides:

- engine status
- health state
- alert explanations
- validation evidence
- configuration advisories

## Controlled Actions

Registered actions:

- `security.validate_config`
- `security.logs.rotate`
- `security.rules.reload`

Current policy:

- Validation enabled
- Mutations disabled

Controlled by:

`EDGE1_OPS_MUTATIONS_ENABLED`

## Evidence

Security evidence location:

`/var/lib/edge1-operations-api/evidence/security`

## Current Validation

Validated:

- Suricata running
- telemetry available
- configuration validation successful
- exporter functioning
- dashboard data available

## Advisory Handling

Expected runtime overrides are classified as informational.

Example:

`wwcx-runtime.yaml` defines the active `wg0` AF_PACKET sensor.
This is expected BigBird deployment behavior.
