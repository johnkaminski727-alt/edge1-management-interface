# Spirit Creek Communications — Hosted Voice Pilot Go/No-Go Plan

**Status:** Planning only; no commercial or production authorization  
**Last updated:** 2026-07-20

## Pilot objective

Evaluate a narrowly scoped, carrier-hosted Saskatchewan business voice service using WW.CX / Edge1 while keeping direct-numbering, production emergency calling, customer porting, contracts, and regulatory submissions behind explicit approval gates.

## Candidate pilot service

- One Saskatchewan local DID in a verified rate centre.
- SIP delivery to an isolated non-production Edge1 test tenant.
- Basic inbound routing, voicemail, and controlled outbound calling.
- Optional SMS/MMS only after DID eligibility and compliance requirements are documented.
- E911 configuration and customer launch only after provider responsibilities, address validation, fees, testing, disclosures, and escalation are separately approved.

## Stage gates

### Gate 0 — identity and authority

**Go when:** legal applicant/billing identity is verified from documentary evidence and the authorized operator is identified.  
**Current state:** `no-go — evidence pending`.

### Gate 1 — carrier evidence

**Go when:** written Saskatchewan inventory, SIP requirements, fraud controls, support path, pricing, reseller rights, portability process, and E911 model are recorded.  
**Current state:** `no-go — substantive provider answers pending`.

### Gate 2 — isolated technical qualification

**Go when:** approved test credentials are available and the carrier qualification matrix passes registration/authentication, inbound/outbound calling, codec, DTMF, caller-ID, failover behavior, fraud controls, CDR, and support escalation tests.  
**Current state:** `not started`.

### Gate 3 — commercial review

**Go when:** all deposits, minimums, recurring charges, usage rates, taxes, contract term, termination, customer ownership, and data-export conditions are reviewed and explicitly accepted by the user.  
**Current state:** `no-go — terms not received or accepted`.

### Gate 4 — safety and compliance

**Go when:** E911 responsibilities, customer disclosures, address workflow, test procedure, outage handling, privacy, call blocking, STIR/SHAKEN responsibilities, abuse response, and messaging compliance are documented and approved.  
**Current state:** `no-go — evidence pending`.

### Gate 5 — controlled launch

**Go when:** a named pilot customer/use case, rollback plan, monitoring, support coverage, change record, and explicit production authorization exist.  
**Current state:** `not authorized`.

## Go criteria

All mandatory gates are green, evidence is current, no material test failure remains, pricing and contracts are approved, and production/E911 authorization is explicit.

## No-go criteria

Any of the following blocks launch:

- unverified legal or billing identity;
- uncertain Saskatchewan DID or porting coverage;
- unclear emergency-calling responsibilities;
- missing fraud/spend controls;
- failed caller-ID, media, DTMF, routing, or support tests;
- undisclosed minimums, deposits, contract commitments, or termination restrictions;
- unsupported customer ownership or portability expectations;
- unresolved security, privacy, regulatory, or operational risk;
- missing rollback, monitoring, or operator coverage.

## Pilot success measures

- Stable call completion and acceptable media quality during the defined test window.
- Correct ANI/DNIS, caller-ID, privacy, DTMF, voicemail, and CDR behavior.
- Fraud controls and alerts verified.
- Support escalation tested without relying on personal contacts.
- Billing matches documented rates.
- Customer-facing availability language accurately reflects evidence.
- All incidents, changes, and outcomes captured in the evidence register.

## Rollback

Rollback means disabling the pilot route, removing the test DID from customer-facing use, revoking test credentials, preserving CDR and audit evidence, reconciling charges, and recording the reason. Number cancellation, port reversal, or contractual termination must follow approved provider procedures.

## Parallel strategic track

Carrier-hosted pilot work must remain separate from direct Canadian numbering and regulatory-readiness work. Pilot completion does not imply OCN, SPID, LRN, LERG, CNAC, CRTC, STIR/SHAKEN, portability, or emergency-service authority.
