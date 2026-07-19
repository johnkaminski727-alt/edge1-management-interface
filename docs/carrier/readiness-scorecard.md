# WW.CX Carrier Readiness Scorecard

**Assessment date:** July 19, 2026  
**Current stage:** Technical foundation / regulatory discovery  
**Launch status:** Not authorized

Scores are planning indicators, not regulatory determinations. A high percentage cannot override an incomplete mandatory gate.

## Scoring method

- 0 — not started
- 1 — discovery
- 2 — planned
- 3 — implementation underway
- 4 — implemented, evidence pending
- 5 — complete and approved

| Domain | Weight | Current score | Weighted readiness | Key observation |
|---|---:|---:|---:|---|
| Corporate eligibility and ownership | 10% | 1/5 | 2% | Canadian applicant and ownership analysis remain unresolved |
| CRTC registration and Proposed CLEC | 12% | 1/5 | 2.4% | Roadmap exists; filings have not been completed |
| Tariffs and carrier agreements | 10% | 0/5 | 0% | Underlying LEC and tariff work remain prerequisites |
| Numbering and portability | 10% | 1/5 | 2% | Architecture concepts exist; operational arrangements do not |
| 9-1-1 and NG9-1-1 | 15% | 0/5 | 0% | No public launch until compliant integration and tests are complete |
| Network and interconnection | 15% | 2/5 | 6% | Edge1, Asterisk, DNS, and SIP work provide a useful foundation |
| STIR/SHAKEN and abuse controls | 8% | 1/5 | 1.6% | Responsibility model and certificate path remain open |
| Customer protection and accessibility | 7% | 0/5 | 0% | CCTS, contracts, disclosures, and accessibility work are pending |
| Security, privacy, and lawful requests | 5% | 2/5 | 2% | Security-minded operations exist but carrier controls need formalization |
| NOC, outage reporting, and continuity | 5% | 1/5 | 1% | Monitoring work exists; formal 24/7 and reporting processes do not |
| Billing and regulatory finance | 3% | 0/5 | 0% | Carrier billing and reconciliation have not been implemented |
| **Total** | **100%** |  | **17%** | **Foundation established; mandatory regulatory and public-safety gates remain open** |

## Gate status

| Gate | Condition | Status |
|---|---|---|
| Gate 1 | Corporate and regulatory eligibility | Open |
| Gate 2 | Proposed CLEC recognition | Open |
| Gate 3 | Technical and operational acceptance | Open |
| Gate 4 | Commercial launch authorization | Open |

## Current strengths

- Edge1 Linux infrastructure and repository governance
- Asterisk/FreePBX operational experience
- SIP, DNS, IPv4, and IPv6 discovery work
- staged-change, validation, rollback, and audit practices
- public interconnect and numbering architecture planning

## Immediate score-improving actions

1. Confirm the Canadian applicant and obtain an ownership/control assessment.
2. Appoint the Response Manager and complete provider registration.
3. Select the initial province, exchanges, service types, and CLEC classification.
4. Solicit qualified underlying Canadian LEC proposals.
5. Define delegated responsibility for numbering, LNP, NG9-1-1, and STIR/SHAKEN.
6. Produce the current-state and target-state network diagrams.
7. Establish a second failure-isolated service path.

## Hard launch blockers

- no final CRTC recognition for the intended CLEC service;
- no compliant 9-1-1/NG9-1-1 arrangement and test evidence;
- no porting arrangement;
- no approved tariff or required intercarrier agreement;
- no customer contracts, emergency disclosures, or CCTS process;
- no controlled production redundancy and outage-response capability.