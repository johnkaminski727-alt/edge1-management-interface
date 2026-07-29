# Suricata Collector Enrichment

Date: 2026-07-29
System: Edge1 / Project Big Bird Operations Center
Status: implemented on feature branch; live activation pending merge

## Objective

Retain the bounded Suricata EVE fields required by the Security Operations drill-down before the shared Big Bird collector publishes `/var/lib/bigbird/operations-center/latest.json`.

## Root cause

The runtime collector was originally installed from the archived WW.CX package:

```text
public/admin/Project-Big-Bird-V4.0.7-Observability-R1/edge/bigbird-ops-collect.py
```

Its `suricata()` function retained only:

- timestamp;
- signature;
- severity;
- category;
- action.

It discarded source and destination addresses, ports, application protocol, SID/GID/revision, and flow identifier before `security_operations_exporter.py` received the snapshot. The exporter and dashboard therefore could not recover those fields.

## Source ownership decision

The authoritative collector source is now:

```text
server/bigbird_ops_collect.py
```

Runtime installation remains:

```text
/usr/local/libexec/bigbird-ops-collect.py
```

The WW.CX website release directory remains an immutable historical release artifact. It is not used as the editable source for ongoing Edge1 collector changes.

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

The source collector remains bounded to the newest 100 alerts from the newest 5,000 EVE lines. The public normalized Security Operations view remains bounded to the newest 50 alerts.

## Privacy boundary

The collector does not publish:

- packet payloads;
- printable payloads;
- packet bodies;
- original nested alert objects;
- raw EVE events;
- credentials;
- private keys;
- arbitrary metadata.

The source snapshot explicitly publishes privacy flags confirming that payloads, raw events, credentials, and private keys are excluded.

## Validation

Automated validation covers:

- representative EVE alert flattening;
- source and destination ports;
- transport and application protocols;
- SID/GID/revision and flow identifier;
- invalid port and negative identifier rejection;
- the 100-alert source bound;
- non-alert event rejection;
- payload, packet, nested alert, metadata, credential, and private-key exclusion;
- deployment-script safety markers and forbidden mutation checks.

## Bounded activation

After merge, activate with:

```bash
cd /opt/edge1-management-interface
git pull --ff-only origin main
sudo bash ./deploy/activate-suricata-collector-enrichment.sh
```

The activator:

1. verifies Edge1, root, `main`, the required collector commit, and clean affected files;
2. records and backs up the current runtime collector and current snapshots;
3. validates the collector, normalized exporter, and privacy tests;
4. stages extraction directly from the live EVE file without publishing;
5. pauses only the existing `bigbird-ops-push.timer`;
6. installs the source-controlled collector and runs the existing one-shot push service;
7. verifies the enriched source snapshot and privacy contract;
8. invokes the existing Suricata normalization activator;
9. verifies the public Security Operations, Correlation, and Network Defense feeds;
10. restores the prior collector and regenerates downstream snapshots automatically on failure.

## Safety boundary

This phase changes only the read-only collector code and derived telemetry snapshots. It does not reload Suricata, change Suricata rules, modify DNS or resolver behavior, alter firewall or nftables rules, change Fail2ban, proxy, routing, authentication, reputation filtering, or traffic controls.
