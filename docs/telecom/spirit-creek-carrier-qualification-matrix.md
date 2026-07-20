# Spirit Creek Communications — Carrier Qualification Matrix

**Status:** Pre-production evaluation framework  
**Last updated:** 2026-07-20  
**Scope:** Standardize evidence collection and technical qualification for VoIP.ms, ThinkTel, Iristel, ISP Telecom, and future Canadian carrier candidates.

## Evidence states

Use only: `verified`, `provider-stated`, `test-passed`, `test-failed`, `pending`, `not-offered`, `non-responsive`, `not-applicable`.

A provider statement is not a test result. Account activation is not commercial acceptance. A DID shown in a portal is not proof of durable inventory or portability coverage.

## Information request

Each carrier should answer the same questions in writing:

### Coverage and numbering

- Saskatchewan DID inventory by NPA, rate centre, and community.
- Local number portability coverage, rejection reasons, documentation, fees, and normal intervals.
- Hosted-numbering model, underlying CLEC/ILEC relationships where discloseable, and future support for customer-held OCN/SPID/LRN resources.
- CNAM, LERG/rating data, directory listing, toll-free, and number aging/quarantine practices.

### SIP and media

- Registration and IP-authentication options.
- Signaling and media addresses, transport, TLS/SRTP support, codec list, DTMF method, fax support, session timers, and maximum channels.
- Caller-ID validation, P-Asserted-Identity handling, diversion/history headers, privacy behavior, and call-forwarding treatment.
- Geographic redundancy, failover design, maintenance notification, and support escalation.

### Safety, fraud, and compliance

- E911 eligibility, address validation, nomadic/fixed treatment, provisioning interval, test-call process, fees, and emergency escalation.
- STIR/SHAKEN attestation responsibilities, traceback cooperation, universal call blocking, robocall mitigation, fraud thresholds, and abuse response.
- International dialing controls, spend limits, concurrent-call controls, IP allowlists, credential rotation, and anomaly notification.

### Messaging and APIs

- Canadian SMS/MMS eligibility by DID type and carrier.
- Registration requirements, throughput, content restrictions, opt-out handling, delivery receipts, media limits, and API rate limits.
- Portal/API support for DIDs, subaccounts, routing, billing, CDRs, E911, messaging, and webhooks.

### Commercial and operational

- Setup charges, deposits, minimum balances, monthly minimums, recurring charges, usage rates, currency, taxes, and credit requirements.
- Reseller and white-label rights, customer ownership, portability rights, termination assistance, data export, and contract term.
- SLA, support hours, severity definitions, escalation contacts, planned maintenance, incident reporting, and service credits.

## Qualification tests

No test below authorizes production traffic or emergency calling.

| Test | Evidence required | Pass condition | Status |
|---|---|---|---|
| Account and portal access | Provider confirmation and controlled operator observation | Account active; no private links stored | `pending` |
| SIP registration | Sanitized test record | Stable registration using approved test credentials | `pending` |
| IP-auth trunking | Provider configuration statement and test record | Calls accepted only from approved source addresses | `pending` |
| Inbound call | Test DID and CDR | Correct destination, ANI, DNIS, audio, teardown | `pending` |
| Outbound call | CDR and provider trace | Correct CLI treatment, audio, teardown | `pending` |
| Codec negotiation | SIP trace summary | Only approved codecs negotiated | `pending` |
| DTMF | Test record | RFC2833/telephone-event works end-to-end | `pending` |
| Caller-ID/privacy | Trace summary | Expected PAI/From/privacy behavior | `pending` |
| Failover | Controlled non-production test | Documented alternate path or clear failure mode | `pending` |
| Fraud controls | Portal/config evidence | Spend, destination, concurrency, and alert controls available | `pending` |
| SMS/MMS | Eligible test DID and delivery evidence | Bidirectional behavior and receipts documented | `pending` |
| Portability dry run | Written procedure only | Required evidence, timing, and rejection path documented | `pending` |
| E911 readiness | Written provider procedure only | Address, activation, test, and escalation process documented | `pending` |
| API | Sanitized API test | Required read/write functions and limits documented | `pending` |
| Support escalation | Ticket evidence | Severity and escalation path confirmed | `pending` |

## Decision gates

A carrier may be recommended for a limited pilot only when:

- Saskatchewan inventory is verified for the intended pilot community;
- SIP, caller-ID, fraud-control, support, and billing requirements are documented;
- E911 responsibilities and activation boundaries are clear before any customer service;
- all pricing and contractual terms have been separately reviewed;
- no unresolved failure creates a safety, legal, portability, or customer-impact risk.

Carrier selection, funding, contracts, live routing, E911 activation, number ports, messaging campaigns, and customer traffic require separate authorization.
