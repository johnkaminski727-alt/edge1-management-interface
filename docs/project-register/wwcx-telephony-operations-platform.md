# WW.CX Telephony Operations Platform Register

## Project status

READ-ONLY FOUNDATION IMPLEMENTED; AUTHENTICATED DTMF, PJSIP ENDPOINT-POLICY, AND LOOPBACK ANALYTICS AUDITS ACCEPTED WITH CARRIER PATHS UNVERIFIED

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
- focused validation script;
- architecture, safety, privacy, collector, validation, and controlled-follow-on documentation;
- read-only Asterisk DTMF capability and endpoint-policy audit;
- offline complete 16-key DTMF generator/detector probe;
- sanitized carrier/interconnect DTMF capability matrix;
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

- telephony, DTMF, endpoint-policy, and analytics validation scripts pass;
- the branch diff contains no credentials or production customer data;
- existing console validation remains green;
- analytics produce only aggregate output from sanitized records;
- no configuration, service-control, call-origination, routing, number-management, emergency-calling, database-query, or carrier write endpoint exists;
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
- carrier, endpoint, trunk, SDP-negotiation, SIP INFO, in-band, and end-to-end behavior remain `unverified`.

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

## Controlled blockers

These items are intentionally outside the autonomous repository foundation:

- production Asterisk AMI/ARI credentials or permission changes;
- production CDR database access;
- carrier API credentials;
- live route, trunk, dial-plan, extension, or registration changes;
- production calls, messages, emergency-calling tests, or number-porting actions;
- STIR/SHAKEN signing or identity-policy changes;
- firewall, DNS, certificate, authentication, or public listener changes;
- automated fraud blocking or traffic enforcement;
- any live DTMF transmission, carrier-path test, or emergency-route test without separate explicit authorization;
- FreePBX database inspection without a separately reviewed metadata-only design and demonstrated need.

## Planned read-only increments

1. populate the sanitized carrier DTMF matrix from reliable provider documentation only;
2. leave unsupported or undocumented carrier capabilities as `unknown`;
3. add sanitized CDR and SIP-event adapters without production credentials or database access;
4. add dashboard panels for health score, failure classes, and carrier performance;
5. add append-only report-generation audit events;
6. add bounded anomaly indicators and investigation links;
7. publish remaining Edge1 deployment and rollback evidence.

## Safety statement

Documentation, registries, tests, health scores, offline signal probes, endpoint-policy reconciliation, and readiness reports do not prove carrier acceptance, regulatory approval, number-allocation authority, portability authority, emergency-services readiness, production certification, NPAS certification, EAS compliance, or Alert Ready conformance.
