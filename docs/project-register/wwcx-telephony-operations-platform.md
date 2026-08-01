# WW.CX Telephony Operations Platform Register

## Project status

READ-ONLY FOUNDATION IMPLEMENTED; AUTHENTICATED DTMF LIVE AUDIT ACCEPTED WITH ONE OPEN EVIDENCE WARNING

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
- authenticated Edge1 DTMF live-acceptance record with protected evidence hashes.

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

- telephony and DTMF validation scripts pass;
- the branch diff contains no credentials or production customer data;
- existing console validation remains green;
- analytics produce only aggregate output from sanitized records;
- no configuration, service-control, call-origination, routing, number-management, emergency-calling, or carrier write endpoint exists;
- review confirms documentation accurately distinguishes local readiness from carrier interoperability and production authorization.

Operational acceptance additionally requires Edge1 execution evidence:

- repository checkout at the accepted commit;
- validation commands and outputs;
- loopback-only service verification where applicable;
- API and browser smoke tests where applicable;
- audit and file-permission inspection;
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
- any live DTMF transmission, carrier-path test, or emergency-route test without separate explicit authorization.

## Planned read-only increments

1. reconcile runtime PJSIP endpoint visibility with authoritative FreePBX and generated endpoint-policy sources;
2. populate the sanitized carrier DTMF matrix from provider documentation only;
3. wire aggregate platform outputs into loopback-only API endpoints;
4. add sanitized CDR and SIP-event adapters;
5. add dashboard panels for health score, failure classes, and carrier performance;
6. add append-only report-generation audit events;
7. add bounded anomaly indicators and investigation links;
8. publish remaining Edge1 deployment and rollback evidence.

## Safety statement

Documentation, registries, tests, health scores, offline signal probes, and readiness reports do not prove carrier acceptance, regulatory approval, number-allocation authority, portability authority, emergency-services readiness, production certification, NPAS certification, EAS compliance, or Alert Ready conformance.
