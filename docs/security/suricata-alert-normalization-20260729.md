# Suricata Alert Normalization

Date: 2026-07-29
System: Edge1 / WW.CX Security Operations
Status: implemented in repository; live deployment pending

## Objective

Replace generic `Unclassified Suricata alert` panels with useful, sanitized investigation records while preserving the read-only and no-payload security boundary.

## Root cause

The dashboard previously preferred a generic explanation title over the nested Suricata signature. It also did not consistently map nested EVE alert severity, rule identifiers, ports, application protocol, or flow identifier into the published Security Operations contract.

The result was an expandable alert that showed a category and action but still reported unknown risk and unknown rule identifiers.

## Normalized contract

The exporter now publishes `schema_version: 2.0` and alert schema `wwcx.suricata-alert.v1`.

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

The expanded alert panel now displays:

- source and destination with ports in the summary;
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
- required UI fields and continued browser no-store behavior.

## Deployment boundary

Deployment requires only:

1. fast-forwarding Edge1 to the merged commit;
2. publishing `src/web/security/index.html` to `/var/www/edge1-status/security/index.html`;
3. running `wwcx-security-operations.service` once to publish schema version 2.0;
4. allowing the existing Security Correlation and Network Defense timers to consume the refreshed snapshot;
5. recording live acceptance evidence.

No Suricata rule reload, Suricata service change, DNS change, firewall change, routing change, Fail2ban change, proxy change, or enforcement activation is required.
