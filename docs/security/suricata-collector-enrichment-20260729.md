# Suricata Collector Enrichment

Date: 2026-07-29
System: Edge1 / Project Big Bird Operations Center
Status: live and accepted

## Objective

Retain the bounded Suricata EVE fields required by the Security Operations drill-down before the shared Big Bird collector publishes `/var/lib/bigbird/operations-center/latest.json`.

## Root cause

The historical runtime collector was installed from the archived WW.CX package:

```text
public/admin/Project-Big-Bird-V4.0.7-Observability-R1/edge/bigbird-ops-collect.py
```

Its `suricata()` function retained only timestamp, signature, severity, category, and action. It discarded addresses, ports, application protocol, SID/GID/revision, and flow identifier before `security_operations_exporter.py` received the snapshot.

## Source ownership

Authoritative source:

```text
server/bigbird_ops_collect.py
```

Runtime installation:

```text
/usr/local/libexec/bigbird-ops-collect.py
```

The WW.CX website release directory remains an immutable historical artifact rather than the editable source for Edge1 collector changes.

## Source alert contract

Collector release:

```text
edge1-suricata-enrichment-r1
```

Source alert schema:

```text
wwcx.suricata-source-alert.v1
```

Allowlisted fields:

- timestamp;
- signature;
- numeric severity;
- category and action;
- source and destination addresses;
- source and destination ports;
- transport protocol;
- application protocol;
- SID, GID, and revision;
- flow identifier or bounded event identifier.

The source collector remains bounded to the newest 100 alerts from the newest 5,000 EVE lines. The public Security Operations view remains bounded to the newest 50 alerts.

## Privacy boundary

The collector does not publish packet payloads, printable payloads, packet bodies, original nested alert objects, raw EVE events, credentials, private keys, or arbitrary metadata.

The source snapshot explicitly marks payloads, raw events, credentials, and private keys as excluded.

## Validation

Automated validation covers:

- representative EVE alert flattening;
- source and destination ports;
- transport and application protocols;
- SID/GID/revision and flow identifier;
- invalid port and negative identifier rejection;
- the 100-alert source bound;
- non-alert event rejection;
- payload, packet, nested-alert, metadata, credential, and private-key exclusion;
- source-contract to public-contract compatibility;
- deployment-script safety markers and forbidden mutation checks.

Both required exact-head workflows passed for PR #115 before merge.

## Delivery

- PR: #115.
- Feature head: `b2e96dd1234b3e87509f0b7e90e6b34ddaf63f73`.
- Merge commit: `21b87664355e5f83173a630f24276389a6dcbbf6`.

## Live activation

Activation command:

```bash
cd /opt/edge1-management-interface
git pull --ff-only origin main
sudo bash ./deploy/activate-suricata-collector-enrichment.sh
```

The activator verified Edge1 and repository state, backed up the prior runtime collector and snapshots, staged live EVE extraction, paused only the existing publisher timer, installed the source-controlled collector, ran the existing one-shot publisher, refreshed the normalized pipeline, verified all public feeds, and preserved rollback evidence.

Authoritative evidence:

```text
/var/lib/wwcx-deployment-evidence/suricata-collector-enrichment/20260729T165711Z
```

## Live acceptance result

The staged and published source snapshot contained 22 alerts. All 22 carried:

- source and destination ports;
- application protocol;
- signature ID;
- generator ID;
- revision;
- flow ID.

The public Security Operations feed also verified 22 classified alerts with known risk, all enrichment fields, cache mode `live`, stale `false`, schema `2.0`, and alert schema `wwcx.suricata-alert.v1`.

Security Correlation refreshed with 22 events and zero correlations. Network Defense remained `limited`, DNS policy remained `not_staged`, enforcement remained disabled, and `traffic_controls_changed` remained `false`.

Nested evidence:

```text
/var/lib/wwcx-deployment-evidence/suricata-collector-enrichment/20260729T165711Z/normalization-activation
/var/lib/wwcx-deployment-evidence/suricata-collector-enrichment/20260729T165711Z/normalization-activation/observability-acceptance
```

## Completion

The upstream collector-field gap is closed for the observed live alerts. The source-controlled collector, normalized exporter, dashboard, correlation, and Network Defense pipeline agree on the enriched read-only contract.

## Safety boundary

This phase changed only read-only collector code and derived telemetry snapshots. It did not reload Suricata, change Suricata rules, modify DNS or resolver behavior, alter firewall or nftables rules, change Fail2ban, proxy, routing, authentication, reputation filtering, or traffic controls.