# Suricata Alert Normalization

Date: 2026-07-29
System: Edge1 / WW.CX Security Operations
Status: implemented, merged, deployed, and live-accepted

## Objective

Replace generic `Unclassified Suricata alert` panels with useful, sanitized investigation records while preserving the read-only and no-payload security boundary.

## Root cause

The dashboard previously preferred a generic explanation title over the nested Suricata signature. It also did not consistently map nested EVE alert severity, rule identifiers, ports, application protocol, or flow identifier into the published Security Operations contract.

The result was an expandable alert that showed a category and action but still reported unknown risk and unknown rule identifiers.

## Normalized contract

The exporter publishes `schema_version: 2.0` and alert schema `wwcx.suricata-alert.v1`.

Allowlisted alert fields are:

- timestamp;
- signature;
- normalized risk;
- original Suricata numeric severity;
- source address and port;
- destination address and port;
- transport protocol;
- application protocol;
- category and action;
- signature ID, generator ID, and revision;
- flow or event identifier;
- bounded meaning and recommendation text;
- explicit sanitization metadata.

The original nested alert object, packet payload, raw packet, raw EVE event, credentials, and private material are not published.

## Risk mapping

Explicit textual risk remains authoritative when present. Otherwise Suricata EVE numeric severity is mapped using the Suricata convention that lower numeric values indicate higher importance:

| Suricata severity | Published risk |
| --- | --- |
| 0 | critical |
| 1 | high |
| 2 | medium |
| 3 | low |
| 4 or greater | informational |
| absent or invalid | unknown |

This mapping is classification only. It does not change Suricata rules, alert actions, firewall behavior, or traffic controls.

## Dashboard behavior

The expanded alert panel displays:

- source and destination with ports in the summary when available;
- Suricata severity;
- separate source and destination ports;
- transport and application protocols;
- category and action;
- SID, GID, revision, and flow/event identifier;
- improved meaning and recommendation text.

Filtering and evidence download include the normalized metadata. Browser requests remain `cache: "no-store"`; the Edge1 last-known-good snapshot cache remains separate and explicitly labeled.

## Validation

Automated validation covers:

- nested EVE-style alert flattening;
- actual signature precedence over the generic explanation title;
- severity-to-risk mapping;
- ports, protocols, identifiers, category, and action;
- rejection of invalid ports and negative identifiers;
- the 50-alert publication bound;
- omission of payload, packet, original nested alert, and raw event data;
- required UI fields and continued browser no-store behavior;
- bounded deployment sequencing and safety controls.

## Live activation

The checked-in activator was executed successfully on Edge1:

```bash
cd /opt/edge1-management-interface
git pull --ff-only origin main
sudo bash ./deploy/activate-suricata-alert-normalization.sh
```

Authoritative evidence:

```text
/var/lib/wwcx-deployment-evidence/suricata-alert-normalization/20260729T082557Z
```

Nested observability acceptance evidence:

```text
/var/lib/wwcx-deployment-evidence/suricata-alert-normalization/20260729T082557Z/observability-acceptance
```

Live acceptance summary:

- 30 alerts published;
- 30 of 30 alerts classified;
- 30 of 30 alerts assigned a known risk;
- cache mode `live` with `stale: false`;
- Security Operations schema `2.0`;
- alert schema `wwcx.suricata-alert.v1`;
- Security Correlation refreshed with 30 events and 0 correlations;
- Network Defense refreshed with overall state `limited`;
- DNS policy state remained `not_staged`;
- enforcement remained disabled;
- `traffic_controls_changed: false`.

## Remaining collector-field gap

The live source snapshot did not include source ports, destination ports, application protocol, or signature IDs for the 30 observed alerts. The normalization layer correctly published these fields as absent rather than inventing values.

Current live counts:

- source port present: 0 of 30;
- destination port present: 0 of 30;
- application protocol present: 0 of 30;
- signature ID present: 0 of 30.

This is an upstream collector/data-contract gap, not a dashboard or cache failure. A future bounded enhancement may update the collector to retain those allowlisted EVE fields, with payload/raw-event exclusion and regression validation preserved.

## Deployment boundary

No Suricata rule reload, Suricata service change, DNS change, firewall change, routing change, Fail2ban change, proxy change, authentication change, or enforcement activation was performed.
