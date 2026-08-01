# WW.CX Telephony Operations Platform Register

## Project status

READ-ONLY FOUNDATION, OFFLINE SANITIZED EVENT ADAPTERS, AGGREGATE CONSOLE PANELS, AND HASH-CHAINED REPORT AUDIT EVENTS IMPLEMENTED; AUTHENTICATED DTMF, PJSIP ENDPOINT-POLICY, AND LOOPBACK ANALYTICS AUDITS ACCEPTED; PARTIAL PROVIDER DTMF EVIDENCE RECORDED WITH CARRIER PATHS UNVERIFIED

This register covers the consolidated Edge1 project for PBX, SIP, carrier, numbering, routing, health, analytics, and AI-assisted operational analysis.

## Objective

Create a safe, privacy-minimized, loopback-only operational platform that reuses the existing Big Bird telephony console and interconnect registry while providing a coherent management and analysis foundation.

## Delivered foundation

- normalized read-only telephony platform module;
- weighted PBX/SIP/routing/registry/analytics health scoring;
- privacy-minimized call-event model;
- aggregate call, carrier, destination, duration, disposition, and SIP-code analytics;
- stable SIP failure classification;
- interconnect state and latency summaries;
- fail-closed offline adapters for already-sanitized CDR and SIP outcome records;
- canonical JSON schemas and synthetic examples for sanitized CDR and SIP inputs;
- negative validation for telephone numbers, SIP URIs, IP and email addresses, caller/callee fields, headers, credentials, SDP, recordings, free-form metadata, unknown fields, and partial-batch acceptance;
- three exact same-origin console routes to the accepted loopback analytics API;
- responsive console panels for health score, call and SIP outcomes, failure classes, sanitized carrier utilization, and aggregate interconnect posture;
- escaped browser rendering and bounded panel-specific unavailable states;
- append-only, owner-only, hash-chained JSONL events for aggregate analytics report generation;
- separate report-audit input and stored-event schemas with synthetic fixtures;
- full-chain, tamper, symlink, permission, malformed-line, and prohibited-field validation;
- focused validation scripts;
- architecture, safety, privacy, collector, validation, and controlled-follow-on documentation;
- read-only Asterisk DTMF capability and endpoint-policy audit;
- offline complete 16-key DTMF generator/detector probe;
- sanitized carrier/interconnect DTMF capability matrix;
- privacy-safe provider evidence intake and first evidence-backed partial matrix entry;
- authenticated Edge1 DTMF live-acceptance record with protected evidence hashes;
- read-only PJSIP runtime-to-generated endpoint-policy reconciliation;
- authenticated PJSIP endpoint-policy live-acceptance record with protected evidence hashes;
- loopback-only read-only analytics API on port `8099`;
- protected analytics live-acceptance audit with payload privacy, method-boundary, runtime source-provenance, and Git-index ownership checks;
- authenticated analytics live-acceptance record with protected evidence hashes.

## Existing platform dependencies

- `server/telephony_status_server.py`
- `src/web/telephony/`
- `src/api/telephony_status_contract.json`
- `data/registry/interconnect/`
- `reports/interconnect-readiness.json`
- telephony deployment and smoke-test scripts
- country, calling-code, timezone, and interconnect registries

## Acceptance criteria

The foundation is accepted at repository level when:

- telephony, sanitized-adapter, console-panel, report-audit, DTMF, endpoint-policy, and analytics validation scripts pass;
- the branch diff contains no credentials or production customer data;
- existing console validation remains green;
- analytics produce only aggregate output from sanitized records;
- adapter inputs fail closed on unsupported or privacy-bearing data and never partially accept a rejected batch;
- browser analytics use only fixed same-origin GET routes, never a user-selected upstream or direct port-`8099` request;
- console values are escaped before insertion into HTML and missing analytics produce bounded unavailable states;
- report-audit events contain only fixed minimized fields and every prior chain entry is validated before append;
- no configuration, service-control, call-origination, routing, number-management, emergency-calling, database-query, collector activation, report scheduling, or carrier write endpoint exists;
- review confirms documentation accurately distinguishes local readiness from carrier interoperability and production authorization.

Operational acceptance additionally requires Edge1 execution evidence:

- repository checkout at the accepted commit;
- validation commands and outputs;
- loopback-only service verification where applicable;
- API and browser smoke tests where applicable;
- audit and file-permission inspection;
- runtime source-provenance verification when a service executes from a separate worktree;
- explicit confirmation that no production routing or customer traffic changed.

## DTMF operational acceptance — 2026-08-01

Authenticated execution on `edge1.ww.cx` as `wwadmin` completed against clean repository head `a600a341bdaaefde8b6bde89cfb9dba48877f500`.

Acceptance record:

```text
docs/telephony/asterisk-dtmf-readiness-live-acceptance-20260801.md
```

Protected evidence:

```text
/var/lib/wwcx-deployment-evidence/asterisk-dtmf-readiness/20260801T073955Z
```

Accepted outcome:

- audit exit code `0`;
- one warning and zero failures;
- Asterisk `22.10.1` running;
- zero active channels, calls, and processed calls;
- local `SendDTMF()` capability advertised `0-9`, `*`, `#`, and `A-D`;
- all sixteen offline DTMF symbols passed;
- RFC 4733 event range recorded as `0-15`;
- repository clean before and after;
- no runtime mutation, channel creation, call origination, or tone transmission.

Open evidence warning:

- no configured PJSIP endpoint DTMF-policy records were found;
- provider-public account-setting documentation now records only an automatic fallback to in-band, without codec, direction, route, or survival evidence;
- provider RFC 4733 event range, endpoint, trunk, SDP negotiation, SIP INFO, extended-key, codec, transcoding, carrier, and end-to-end behavior remain `unknown` or `unverified` as applicable.

## Provider-public DTMF evidence repository acceptance — 2026-08-01

Repository merge `31fb4865f409bcf474ffd3d2c61a1727161cbe4c` accepted the first privacy-minimized provider-public capability entry.

Acceptance record:

```text
docs/telephony/dtmf-provider-public-evidence-acceptance-20260801.md
```

Accepted outcome:

- a validated provider-public evidence record uses sanitized provider and route identifiers only;
- the capability matrix records `inband.status=documented` with no codec constraint;
- the evidence states only that an account-level automatic mode can fall back to in-band;
- RFC 4733 remains `unknown` because the public legacy RTP-event terminology does not state an event range;
- SIP INFO, extended `A-D`, exact directionality, codec and transcoding behavior, and end-to-end interoperability remain unknown;
- carrier interoperability is only `partially-documented`;
- live-test authorization remains false;
- the matrix validator now requires every entry and capability claim to match a privacy-validated evidence record and retained evidence reference;
- no provider identity, customer identifier, credential, telephone number, SIP URI, private endpoint, call, DTMF transmission, route change, or runtime mutation was introduced.

## PJSIP endpoint-policy operational acceptance — 2026-08-01

Authenticated execution on `edge1.ww.cx` as `wwadmin` completed against clean repository head `6906d1bb7f5aa517c249bf893ab23675b63f062f`.

Acceptance record:

```text
docs/telephony/asterisk-pjsip-endpoint-policy-live-acceptance-20260801.md
```

Protected evidence:

```text
/var/lib/wwcx-deployment-evidence/asterisk-pjsip-endpoint-policy/20260801T085814Z
```

Accepted outcome:

- audit exit code `0`;
- two informational warnings and zero failures;
- Asterisk `22.10.1` running with zero active channels, calls, and processed calls;
- zero runtime endpoints, AORs, contacts, and transports;
- 23 generated PJSIP configuration files inspected;
- zero explicit generated endpoint-policy records;
- runtime and generated endpoint counts matched at zero;
- FreePBX CLI `17.0.30` present;
- FreePBX source metadata and hashes recorded without reading source contents;
- no database query, credential read, endpoint identifier retention, call, channel, DTMF transmission, or runtime mutation.

Decision:

- the active runtime/generated configuration conclusion is complete without a database query;
- dormant, historical, backup, module-private, or externally provisioned data remains outside the acceptance;
- database inspection is deferred unless a narrower operational need is established and separately reviewed;
- carrier and end-to-end behavior remain `unverified`.

## Telephony analytics operational acceptance — 2026-08-01

Authenticated execution on `edge1.ww.cx` as `wwadmin` completed against clean repository head `cb7c5174fa17e9c145ec549e8a8b7d29ac3cc628`.

Acceptance record:

```text
docs/telephony/telephony-analytics-live-acceptance-20260801.md
```

Protected analytics evidence:

```text
/var/lib/wwcx-deployment-evidence/telephony-analytics-live-acceptance/20260801T191636Z
```

Analytics evidence-manifest SHA-256:

```text
31a21acfe7888bfcab971af6de8b7aa4c23ff22fe31ae56fdc99ad9a54e1b336
```

Protected repository-metadata evidence:

```text
/var/lib/wwcx-deployment-evidence/repository-metadata-repair/20260801T191636Z
```

Repository-metadata evidence-manifest SHA-256:

```text
ba5c949567b7dd8655dd7dbe76d75bc69dcb96f988cf46517148bd9b9abfc4cf
```

Accepted outcome:

- audit exit code `0`;
- zero warnings and zero failures;
- `wwcx-telephony-analytics.service` active and enabled under `wwadmin`;
- hardening properties confirmed;
- loopback-only listener on `127.0.0.1:8099`;
- health, platform-health, call-summary, and interconnect-summary endpoints validated;
- POST rejected with HTTP `405`;
- payload-contract and privacy validation passed;
- runtime analytics API and platform files matched canonical repository SHA-256 hashes;
- root-run audit preserved `.git/index` ownership as `wwadmin:wwadmin`;
- repository clean before and after;
- no service restart, runtime mutation, call, DTMF, database query, credential read, carrier route change, firewall change, DNS change, certificate change, or public exposure.

Decision:

- the loopback-only read-only aggregate analytics service is operationally accepted;
- the alternate runtime worktree is accepted for the measured source hashes only;
- production CDR/SIP collectors, carrier integrations, database access, write operations, and public exposure remain outside acceptance.

## Sanitized event-adapter repository acceptance — 2026-08-01

Repository assets:

```text
server/telephony_sanitized_adapters.py
schemas/telephony/sanitized-cdr-record.schema.json
schemas/telephony/sanitized-sip-event.schema.json
examples/telephony/sanitized-cdr-record.example.json
examples/telephony/sanitized-sip-event.example.json
tests/validate_telephony_sanitized_adapters.py
docs/telephony/sanitized-event-adapters.md
```

Accepted boundary:

- inputs must already be sanitized before reaching the adapters;
- records use explicit scalar allowlists and schema version `1.0`;
- CDR and SIP aliases normalize only into the common `CallEvent` model;
- SIP outcomes derive only conservative progress, completed, failed, or unknown dispositions;
- unsupported fields and privacy-bearing values are rejected;
- invalid batches fail without returning a partial result;
- adapter output metadata is limited to adapter identity, schema version, opaque source record ID, UTC observation time, and SIP operational event type;
- no file, database, network, credential, service-control, PBX, carrier, route, or configuration access exists in the adapter module;
- no live collector, source connection, data-file change, service change, or runtime deployment is included.

## Analytics console-panel repository acceptance — 2026-08-01

Repository assets:

```text
server/telephony_status_server.py
src/web/telephony/index.html
src/web/telephony/telephony.js
src/web/telephony/telephony.css
tests/validate_telephony_analytics_console_panels.py
docs/telephony/analytics-console-panels.md
```

Accepted boundary:

- the browser uses only three exact same-origin analytics routes;
- the console server maps those routes to fixed `127.0.0.1:8099` GET endpoints;
- there is no wildcard, query-selected, path-selected, or user-selected upstream proxy;
- the browser never directly addresses port `8099`;
- health, call/SIP outcome, and carrier/interconnect panels render only aggregate responses;
- every value used in HTML templates is escaped;
- each analytics request fails independently and a missing upstream returns HTTP `503` with a bounded unavailable state;
- no fixture fabricates aggregate analytics values;
- no POST, PUT, PATCH, DELETE, service-control, telephony write, database, credential, route, or public-listener capability is introduced;
- repository implementation does not install, restart, reload, or deploy either service;
- live console deployment and rendered acceptance remain separately gated.

## Analytics report-audit repository acceptance — 2026-08-01

Repository assets:

```text
server/telephony_report_audit.py
tools/telephony/append_analytics_report_audit.py
schemas/telephony/analytics-report-audit-input.schema.json
schemas/telephony/analytics-report-audit-event.schema.json
examples/telephony/analytics-report-audit-input.example.json
examples/telephony/analytics-report-audit-event.example.json
tests/validate_telephony_report_audit.py
docs/telephony/analytics-report-audit-events.md
```

Accepted boundary:

- the module records only that an already-generated aggregate report was produced;
- input and stored events use fixed field allowlists and a fixed privacy profile;
- event/report/generator identifiers are opaque and bounded;
- report kinds are limited to health, call, interconnect, or combined summaries;
- report content, paths, names, telephone or account numbers, SIP/TEL URIs, email or IP addresses, route identifiers, credentials, message bodies, SDP, media, recordings, and free-form metadata are absent;
- logs must be absolute owner-only regular `.jsonl` files below an existing non-symlink parent;
- the final path is opened with `O_NOFOLLOW`, append operations use `O_APPEND`, and verification/appends use file locks;
- every prior event and SHA-256 link is validated before append;
- canonical JSON is newline-terminated and fsynced;
- changed events, broken chains, malformed final lines, symlinks, broad permissions, unsafe paths, unknown fields, and invalid values fail closed;
- no report generator, runtime directory, service, timer, live event append, data-source access, telephony action, or deployment is included.

## Controlled blockers

These items are intentionally outside the autonomous repository foundation:

- production Asterisk AMI/ARI credentials or permission changes;
- production CDR database access;
- connecting live CDR, SIP-edge, AMI/ARI, log, packet, or carrier sources to the offline adapters;
- deployment or restart of the running console service without a bounded source and rollback check;
- creation of a live report job, audit directory, retention policy, timer, or service without separate review and authorization;
- carrier API credentials;
- live route, trunk, dial-plan, extension, or registration changes;
- production calls, messages, emergency-calling tests, or number-porting actions;
- STIR/SHAKEN signing or identity-policy changes;
- firewall, DNS, certificate, authentication, or public listener changes;
- automated fraud blocking or traffic enforcement;
- any live DTMF transmission, carrier-path test, or emergency-route test without separate explicit authorization;
- FreePBX database inspection without a separately reviewed metadata-only design and demonstrated need.

## Planned read-only increments

1. obtain provider-specific RFC 4733 event-range, SIP INFO, codec, transcoding, direction, SBC, regional, and extended-key documentation;
2. leave every unsupported or undocumented carrier capability as `unknown`;
3. keep carrier and end-to-end paths unverified until separately authorized controlled-test evidence exists;
4. add bounded anomaly indicators and investigation links;
5. design live source-minimization collectors only after access, privacy, retention, and rollback review;
6. design a report generator and runtime audit retention model without deploying them;
7. prepare and separately authorize bounded console deployment and live verification;
8. publish remaining Edge1 deployment and rollback evidence.

## Safety statement

Documentation, schemas, adapters, panels, report-audit events, registries, tests, health scores, offline signal probes, endpoint-policy reconciliation, and readiness reports do not prove carrier acceptance, regulatory approval, number-allocation authority, portability authority, emergency-services readiness, production certification, NPAS certification, EAS compliance, or Alert Ready conformance.
