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

Authoritative source:

- `server/bigbird_ops_collect.py`

Runtime installation:

- `/usr/local/libexec/bigbird-ops-collect.py`

Publisher service and timer:

- `bigbird-ops-push.service`
- `bigbird-ops-push.timer`

Publishes security telemetry into:

- `/var/lib/bigbird/operations-center/latest.json`

The source collector publishes the bounded alert schema
`wwcx.suricata-source-alert.v1`. It retains only allowlisted alert metadata
required for investigation and excludes packet payloads, raw EVE events,
credentials, private keys, original nested alert objects, and arbitrary
metadata.

The older copy under the archived WW.CX Project Big Bird V4.0.7 release
package is historical release evidence and is not the editable Edge1 source.

### Exporter

Path:

- `server/security_operations_exporter.py`

Publishes:

- `/var/www/edge1-status/security-operations.json`

The exporter converts the source collector contract into Security Operations
schema `2.0` and alert schema `wwcx.suricata-alert.v1`, applies the public
50-alert bound, and provides last-known-good fallback metadata.

### Dashboard

Path:

- `src/web/security/index.html`

Provides:

- engine status
- health state
- alert explanations
- accessible alert drill-down
- validation evidence
- configuration advisories
- live versus stale-cache status

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

Collector enrichment deployment evidence:

`/var/lib/wwcx-deployment-evidence/suricata-collector-enrichment/<timestamp>`

## Current Validation

Validated:

- Suricata running
- telemetry available
- configuration validation successful
- exporter functioning
- dashboard data available
- alert expand/collapse functioning
- last-known-good cache functioning
- nested alert classification and risk normalization functioning

Collector field enrichment is implemented in the repository. Live acceptance
must verify that the current EVE stream supplies ports, identifiers, and flow
metadata after the enriched collector is installed.

## Advisory Handling

Expected runtime overrides are classified as informational.

Example:

`wwcx-runtime.yaml` defines the active `wg0` AF_PACKET sensor.
This is expected BigBird deployment behavior.
