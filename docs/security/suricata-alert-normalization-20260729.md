# Suricata Alert Normalization

Date: 2026-07-29
System: Edge1 / WW.CX Security Operations
Status: implemented and merged; bounded live activation script available

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

## Bounded live activation

Use the checked-in activator instead of pasting a large here-document:

```bash
cd /opt/edge1-management-interface
git pull --ff-only origin main
sudo bash ./deploy/activate-suricata-alert-normalization.sh
```

The activator:

1. verifies the Edge1 host, root principal, `main` branch, required merge commit, and absence of local changes in the affected files;
2. runs the cache, normalization, UI, Python compile, and inline JavaScript syntax validations;
3. stages Security Operations, Security Correlation, and Network Defense output in the evidence directory before publication;
4. validates schema version 2.0, the sanitized alert contract, read-only correlation, disabled DNS enforcement, and unchanged traffic controls;
5. publishes the dashboard page and refreshes the three existing one-shot exporters in dependency order;
6. verifies all HTTPS pages and JSON feeds through `edge1.ww.cx`;
7. runs the established Security observability acceptance verifier;
8. captures systemd status, journals on failure, hashes, acceptance summaries, and a timestamped evidence path.

The previous live dashboard page is restored automatically if activation fails after publication. Runtime JSON snapshots are preserved in the evidence directory for diagnosis.

## Deployment boundary

No Suricata rule reload, Suricata service change, DNS change, firewall change, routing change, Fail2ban change, proxy change, authentication change, or enforcement activation is performed.
