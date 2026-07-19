# WW.CX Canadian Carrier Readiness Roadmap

**Status:** Working public roadmap  
**Prepared:** July 19, 2026  
**Scope:** CRTC registration, Proposed CLEC to CLEC progression, interconnection, numbering, portability, 9-1-1/NG9-1-1, STIR/SHAKEN, Edge1 infrastructure, operations, security, billing, customer protection, and launch governance.

> This is an implementation-planning document, not legal advice. Canadian telecommunications counsel should validate the applicant entity, ownership and control, CLEC classification, tariffs, agreements, and filing strategy before service launch.

## Executive direction

WW.CX should pursue a partner-assisted Canadian carrier entry model first. The initial target should be assessed as a possible Type IV or Type III CLEC arrangement, with selected regulated functions supplied by a qualified underlying Canadian local exchange carrier. WW.CX can then migrate toward greater network, numbering, interconnection, and operational independence as its subscriber base and capabilities grow.

The recommended sequence is:

1. Confirm the Canadian applicant entity and ownership/control eligibility.
2. Freeze the initial service model, province, exchanges, and customer class.
3. Register as a telecommunications provider and establish CRTC Data Collection System access.
4. Determine whether a Basic International Telecommunications Services licence is required.
5. Apply for recognition as a Proposed CLEC.
6. Select an underlying Canadian LEC and document every delegated obligation.
7. File and obtain approval for the applicable tariff and agreements.
8. Implement numbering, portability, 9-1-1/NG9-1-1, STIR/SHAKEN, customer safeguards, and CCTS participation.
9. Convert Edge1 into one component of a resilient, monitored, failure-isolated carrier platform.
10. Complete regulatory, technical, operational, and customer acceptance testing.
11. Submit completion evidence and obtain authorization to operate as a CLEC.
12. Launch through internal, invitation-only, and limited commercial pilots before general availability.

## Program gates

### Gate 1 — Corporate and regulatory eligibility

Required evidence:

- Canadian legal applicant identified.
- Directors, officers, beneficial ownership, voting rights, financing, and related companies documented.
- Canadian ownership and control assessed by qualified counsel.
- Initial CLEC classification documented.
- Initial provinces, exchanges, services, and customer classes approved.
- International-carriage and BITS applicability determined.

### Gate 2 — Proposed CLEC recognition

Required evidence:

- Telecommunications-provider registration completed.
- Response Manager and alternate appointed.
- My CRTC Account and Data Collection System access established.
- Proposed CLEC filing submitted.
- CRTC recognition letter received.
- No public CLEC service offered before completion of applicable entry requirements.

### Gate 3 — Technical and operational acceptance

Required evidence:

- Underlying carrier and interconnection agreements executed.
- Applicable tariff approved.
- Numbering inventory and conservation controls active.
- Port-in and port-out tests passed.
- 9-1-1/NG9-1-1 routing and location tests passed through approved procedures.
- STIR/SHAKEN signing and verification tested.
- CCTS participation completed.
- Accessibility, privacy, security, outage reporting, billing, support, and disaster recovery controls tested.
- No critical unresolved launch risk.

### Gate 4 — Controlled commercial launch

Required evidence:

- CRTC completion recognition obtained.
- Internal pilot completed.
- Invitation pilot metrics accepted.
- Emergency calling, number routing, billing, porting, monitoring, and support remain stable.
- Commercial launch authorization signed by WW.CX leadership.

## Phase 0 — Governance and evidence

Create a carrier program charter, regulatory obligations register, risk register, decision log, evidence index, document-retention policy, and formal change-management process. Every obligation should have a source, applicability determination, owner, status, evidence location, review date, risk, and dependency.

Production-impacting changes to SIP routing, 9-1-1, numbering, DNS, firewall policy, certificates, caller identity, portability, or interconnection must require a change record, test plan, rollback plan, approval, and retained post-change evidence.

## Phase 1 — Corporate eligibility and service definition

Document the applicant's legal name, jurisdiction, registered office, directors, officers, shareholders, beneficial ownership, financing arrangements, affiliates, and trade names. Obtain Canadian telecommunications counsel to assess carrier status, ownership and control, Type IV/III/I treatment, international carriage, privacy, lawful access, tariffs, and provincial consumer obligations.

Freeze the first service definition, including whether WW.CX will offer residential local VoIP, business local VoIP, SIP trunks, inbound numbers, outbound calling, toll-free, long distance, international calling, fixed service, nomadic service, or hosted PBX. Select the first province, ILEC territory, exchanges, rate centres, and customer limits.

## Phase 2 — CRTC registration and regulatory accounts

Appoint a Response Manager and alternate. Establish My CRTC Account and Data Collection System access. Register the legal entity as a telecommunications provider and create a filing calendar for annual registration updates, ownership filings, surveys, revenue forms, accessibility reports, BITS reporting, and other assigned returns.

Determine whether any signalling, media, switching, or wholesale arrangement carries telecommunications traffic between Canada and another country. Apply for a BITS licence before international carriage when required.

## Phase 3 — Proposed CLEC filing

Prepare a filing package containing corporate information, ownership/control attestation, requested CLEC classification, intended provinces and exchanges, service description, underlying-carrier model, facilities description, compliance attestation, implementation plan, and proposed launch sequence.

Track all CRTC correspondence and requests for information. Proposed CLEC recognition is a project milestone, not authorization for public CLEC service.

## Phase 4 — Underlying carrier and interconnection partners

Evaluate Canadian carriers for exchange coverage, number availability, porting, NG9-1-1, STIR/SHAKEN, SIP TLS, media security, IPv4/IPv6, redundancy, regulatory cooperation, incident response, audit evidence, pricing, financial stability, and transition support.

The contract must explicitly state which party performs each obligation, the evidence supplied to WW.CX, audit rights, outage-notification timing, data ownership, number migration rights, continuity protections, and termination assistance.

## Phase 5 — Tariffs and regulated agreements

Select the current CRTC model tariff for the approved CLEC type. Populate company, service territory, rates, references, billing conditions, interconnection terms, and dispute provisions. Identify and justify any deviation from the model. File required agreements and establish annual tariff review and version control.

## Phase 6 — Numbering

Begin with hosted or wholesale numbering unless direct assignments are justified. Maintain a number inventory containing the telephone number, exchange, NPA-NXX or block, underlying carrier, customer, service address, emergency address, route, activation state, port state, quarantine state, aging date, and release date.

Implement utilization thresholds, assignment justification, quarantine, return of unused resources, reconciliation with partner records, and forecasts. Maintain a future path for CNA applications, identifiers, direct assignments, pooling, utilization reporting, and routing-database participation.

## Phase 7 — Local number portability

Build documented port-in and port-out workflows covering authorization, validation, account information, service address, due dates, firm order confirmation, rejection handling, emergency-record coordination, cutover testing, customer notification, fraud review, slamming disputes, cancellation, rollback, and evidence retention.

Complete controlled test ports in both directions before launch.

## Phase 8 — 9-1-1 and NG9-1-1

Classify each product as fixed, nomadic, non-native, residential, business, multi-line, reseller-based, or facilities-based. Document emergency-call recognition, routing, callback identity, location delivery, failure behavior, unregistered-location handling, and emergency-call precedence.

Maintain a validated customer-location database with audit history and synchronization to the emergency-services provider. Provide clear customer disclosures for power loss, Internet loss, nomadic use, location updates, and routing limitations. Retain acknowledgement evidence.

Use approved test numbers and coordinated procedures; never place uncontrolled test calls to live emergency centres. Test location, callback number, route, failover, porting, address changes, and service suspension. Address multi-line telephone system requirements for hosted PBX customers.

## Phase 9 — Edge1 carrier architecture

Edge1 must not remain a single point of failure for SIP registration, inbound or outbound calls, DNS, customer authentication, emergency calling, number routing, billing authorization, monitoring, or configuration storage.

The target architecture should include:

- redundant session border control and signalling paths;
- redundant call-control nodes;
- redundant media relays where required;
- resilient customer, number, routing, emergency-location, and billing data;
- restricted management access with MFA and least privilege;
- configuration versioning, tested backups, and secrets management;
- redundant authoritative DNS and controlled SIP records;
- synthetic inbound and outbound call monitoring;
- certificate, SIP, RTP, DNS, disk, database, capacity, and reachability monitoring;
- a second failure-isolated service location or equivalent managed-carrier design.

Experimental SIP work must remain separated from existing FreePBX service until formally accepted.

## Phase 10 — SIP interconnection and security

Define interconnect FQDNs, IP allowlists, certificate identities, SIP domains, asserted-identity policy, privacy behavior, and route-set expectations. Implement SIP TLS with monitored certificate renewal and approved cipher policy. Use SRTP where supported and operationally compatible.

Normalize E.164 addressing, Canadian dialing, emergency numbers, P-Asserted-Identity, Privacy, Diversion, History-Info, transfers, session timers, early media, DTMF, fax, codecs, and error handling. Protect interconnects through topology hiding, source validation, transaction and call-rate limits, malformed-message controls, fraud controls, destination restrictions, and anomaly detection.

## Phase 11 — STIR/SHAKEN and robocall mitigation

Select whether WW.CX signs directly, the underlying carrier signs on its behalf, or a hybrid model is used. Document certificate governance, attestation policy, customer identity verification, number authorization, inbound verification, revocation, traceback response, complaint correlation, traffic analytics, and abusive-account suspension.

Customers must not be able to present unauthorized Canadian calling numbers. Signing decisions and verification outcomes must be auditable.

## Phase 12 — Customer safeguards and CCTS

Join and fund the Commission for Complaints for Telecom-television Services as required. Create customer agreements covering service, price, term, cancellation, equipment, acceptable use, number assignment, portability, 9-1-1 limitations, power and Internet dependencies, privacy, suspension, fraud, service credits, complaints, and CCTS information.

Retain evidence of service orders, contract acceptance, port authorization, emergency disclosures, and material changes. Build complaint workflows for billing, contract, quality, outages, porting, emergency service, caller identity, privacy, accessibility, fraud, and unwanted calls.

## Phase 13 — Privacy, security, lawful requests, and records

Complete a privacy impact assessment and data-flow map for identity, billing, call-detail records, SIP logs, IP addresses, location, emergency records, recordings, credentials, and support communications. Document all countries in which data is stored or processed.

Implement retention schedules, MFA, least privilege, encrypted backups, secrets management, patching, vulnerability scanning, endpoint controls, centralized logging, immutable audit records, segmentation, supplier review, incident response, breach response, and penetration testing.

Create a counsel-reviewed process for validating and responding to lawful requests, emergency requests, evidence preservation, disclosure limitation, audit logging, and confidentiality.

## Phase 14 — Accessibility

Determine the entity's classification and reporting duties under the Accessible Canada Act framework administered by the CRTC. Establish an accessibility feedback process, required plans and progress reports, accessible support channels, alternate formats, relay-related support, accessible emergency information, website testing, and staff training.

## Phase 15 — Reliability and outage reporting

Create 24/7 operational coverage, an on-call schedule, severity levels, partner escalation, emergency escalation, customer communications, and regulatory escalation. Monitor service proactively rather than relying on customer complaints.

Build a major-outage decision process considering customer count, duration, geography, total loss or degradation, emergency-service impact, accessibility-service impact, traffic volume, partner events, and cybersecurity. Maintain ready-to-use CRTC, ISED, carrier, authority, and customer notification templates. Conduct post-incident reviews with tracked corrective actions.

## Phase 16 — Billing, finance, and regulatory costs

Implement a reproducible billing ledger for recurring charges, usage, tax, one-time charges, credits, refunds, partner costs, disputes, suspension, and final bills. Reconcile Edge1, SBC, softswitch, partner, invoice, and customer records. Preserve immutable raw call records and versioned rates.

Assess CRTC fees, contribution reporting, CCTS fees, numbering and portability costs, emergency-service charges, taxes, security costs, insurance, deposits, and legal expenses. Maintain a funded three-year carrier plan.

## Phase 17 — Vendors, insurance, and continuity

Assess insurance for general liability, errors and omissions, cyber risk, privacy breach, business interruption, equipment, and directors and officers. Maintain a critical-vendor register covering financial health, geographic concentration, subcontractors, data location, support, recovery, regulatory status, and transition assistance.

Protect customer numbers, routing data, service records, and migration rights contractually. Develop substitutes for origination, termination, DNS, certificates, monitoring, hosting, and other critical services where feasible.

## Phase 18 — Completion and acceptance

Before seeking final CLEC recognition, verify registration, ownership, tariffs, agreements, BITS status, CCTS, accessibility, numbering, portability, emergency service, STIR/SHAKEN, resilience, customer contracts, billing, support, outage reporting, security, backup, failover, and disaster recovery.

Submit a completion package with an obligation matrix, attestations, tariff and agreement references, service territory, delegated-obligation evidence, emergency-service confirmation, portability confirmation, technical readiness summary, contacts, and requested effective date.

## Phase 19 — Controlled launch

Launch in four stages:

1. Internal pilot.
2. Invitation-only pilot.
3. Limited commercial availability in selected exchanges.
4. General availability after metrics and risk review.

Stop new activations immediately for an emergency-routing defect, systemic number-routing error, unauthorized caller-ID signing, uncontrolled toll fraud, billing corruption, inability to port out, major security breach, repeated severe outage, or missing authorization.

## Phase 20 — Ongoing compliance

Monthly: reconcile number inventory, certificates, emergency-location exceptions, fraud, vulnerabilities, partner SLAs, and complaints.

Quarterly: review obligations, access, call quality, portability, supplier risk, disclosures, and a sample restore or failover exercise.

Semi-annually: review STIR/SHAKEN reporting, emergency-call procedures, outage readiness, tariff changes, and security exercises.

Annually: complete assigned DCS filings, ownership updates, BITS updates, accessibility filings, CCTS requirements, penetration testing, disaster recovery, tariff review, insurance renewal, CLEC classification review, and counsel review.

Reassess classification and architecture as subscriber count grows, resale dependence changes, direct numbering is pursued, new facilities are operated, additional LECs are interconnected, or new provinces and service classes are added.

## Immediate WW.CX work queue

1. Create the regulatory obligations and evidence registers.
2. Confirm the Canadian applicant and ownership/control eligibility.
3. Appoint telecom counsel and a Response Manager.
4. Freeze the first province, exchanges, services, and customer limits.
5. Determine Type IV versus Type III treatment.
6. Complete provider registration and BITS analysis.
7. Prepare the Proposed CLEC filing.
8. Issue a wholesale-partner requirements document.
9. Obtain proposals for numbering, portability, NG9-1-1, and STIR/SHAKEN.
10. Prepare the applicable model tariff.
11. Complete Edge1 address, routing, SIP, certificate, and dependency inventories.
12. Build a staging interconnect isolated from production FreePBX.
13. Design the second failure-isolated call path.
14. Draft customer contracts, emergency disclosures, privacy documents, and complaint procedures.
15. Build number inventory, emergency-location, porting, billing, monitoring, outage, and evidence systems.

## Highest-priority unresolved decisions

- Exact Canadian legal applicant and ownership/control status.
- First province, exchange, and customer class.
- Fixed, nomadic, or mixed VoIP treatment.
- Type IV or Type III initial classification.
- Underlying Canadian LEC.
- Party responsible for number portability.
- Party responsible for NG9-1-1 connectivity.
- Party responsible for STIR/SHAKEN signing.
- Whether signalling or media crosses Canada’s border.
- BITS licence applicability.
- Geographic redundancy design for Edge1.
- Residential, business, wholesale, or mixed launch.
- Pilot customer and traffic limits.
- Approved compliance and interconnection budget.

## Current readiness assessment

WW.CX already has useful building blocks: Linux infrastructure, Asterisk and FreePBX experience, SIP and TLS planning, public DNS, IPv4/IPv6 investigation, interconnect planning, repository governance, staged configuration management, rollback discipline, security-conscious deployment, and an operational evidence library.

The material gaps are the confirmed Canadian applicant, CLEC classification, formal registration, Proposed CLEC filing, BITS determination, underlying carrier agreement, tariff approval, selected exchanges, NG9-1-1 integration, portability, STIR/SHAKEN production responsibility, CCTS participation, accessibility program, outage reporting, geographic redundancy, carrier billing, number inventory, and controlled acceptance tests.

## Public references

- CRTC telecommunications provider registration: https://crtc.gc.ca/eng/comm/telecom/registr.htm
- CRTC local exchange carrier entry requirements: https://crtc.gc.ca/eng/comm/telecom/eslcclec.htm
- CRTC international telecommunications licensing: https://crtc.gc.ca/eng/comm/telecom/international.htm
- CRTC 9-1-1 obligations: https://crtc.gc.ca/eng/phone/911/serv.htm
- CRTC outage notification and resilience: https://crtc.gc.ca/eng/comm/telecom/notifresilienc.htm
- Canadian Numbering Administrator: https://www.cnac.ca/

## Conclusion

WW.CX has a credible technical starting point but is not yet ready to operate publicly as a Canadian CLEC. The safe path is:

**Canadian entity and eligibility → provider registration → Proposed Type IV or Type III CLEC → qualified underlying Canadian LEC → tariffs and agreements → numbering, portability, NG9-1-1, STIR/SHAKEN, resilience, customer safeguards, and operational acceptance → CRTC completion recognition → controlled pilot → limited commercial launch.**
