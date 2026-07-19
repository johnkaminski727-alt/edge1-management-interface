# Spirit Creek Communications — Canadian Carrier Comparison

**Status:** Preliminary evidence-based comparison  
**Last updated:** 2026-07-19  
**Applicant identity:** Spirit Creek Communications (Canada-incorporated; exact legal corporate name and corporation number pending documentary verification)  
**Technical platform:** WW.CX / Edge1

Status values: `verified`, `provider-stated`, `pending`, `not offered`, `non-responsive`, `not applicable`.

Unknown values are not inferred. A provider capability statement is not proof of Saskatchewan inventory, commercial acceptance, account activation, or service availability for a specific rate centre.

| Category | VoIP.ms | ThinkTel | Iristel | ISP Telecom |
|---|---|---|---|---|
| Saskatchewan coverage | `pending` — provider states Canadian DIDs are available in many rate centres; Regina, Saskatoon, Yorkton, Invermay-area, and eastern Saskatchewan inventory not yet verified | `pending` — tickets 12603061 and 12603062 opened; no substantive coverage answer | `non-responsive` — inquiry sent; no substantive answer | `non-responsive` — inquiry sent; no substantive answer |
| Portability | `provider-stated` — local-number portability supported subject to eligibility; provider stated about five business days after complete documentation and no fee for local ports | `pending` | `pending` | `pending` |
| SIP | `provider-stated` — Asterisk and FreePBX supported using standard SIP credentials; inbound and outbound calling offered | `pending` | `pending` | `pending` |
| Messaging | `provider-stated` — SMS on eligible DIDs, SMS API, and MMS on supported numbers; Saskatchewan number eligibility pending | `pending` | `pending` | `pending` |
| Emergency calling | `provider-stated` — E911 available on eligible DIDs; provider quoted USD 1.50 activation plus USD 1.50 monthly per enabled DID; provisioning details and Saskatchewan eligibility pending | `pending` | `pending` | `pending` |
| STIR/SHAKEN | `pending` | `pending` | `pending` | `pending` |
| Call blocking | `pending` | `pending` | `pending` | `pending` |
| Numbering | `pending` — hosted LRN, NPAC/LNP, and future direct-numbering support not confirmed in writing | `pending` | `pending` | `pending` |
| Routing data | `pending` — LERG and rating support not confirmed | `pending` | `pending` | `pending` |
| Operations | `provider-stated` — customer portal, API documentation, reseller portal, and support-ticket system identified; escalation contacts and SLAs pending | `pending` | `pending` | `pending` |
| Commercial | `provider-stated` — pay-as-you-go model stated; E911 fees quoted; full pricing, minimum balance, deposits, account minimums, and wholesale terms pending | `pending` | `pending` | `pending` |
| Resale | `provider-stated` — reseller program and customer/DID/billing management available; exact terms pending | `pending` | `pending` | `pending` |
| Strategic fit | `pending` — strongest documented hosted-launch capability so far, but activation and Saskatchewan-specific evidence remain blockers | `pending` | `pending` | `pending` |

## Preliminary recommendation

No final carrier recommendation is justified yet.

VoIP.ms currently has the most complete written capability response and appears suitable for a hosted proof-of-concept or early launch evaluation. That is not a selection or acceptance. The account remains unverified as active, Saskatchewan DID/rate-centre inventory is unconfirmed, and hosted numbering, emergency-service, routing, support, and commercial details remain incomplete.

ThinkTel, Iristel, and ISP Telecom cannot be ranked until substantive written responses are received. ThinkTel ticket acknowledgements are evidence only that requests were opened.

## Evidence still required before selection

- Written Saskatchewan inventory and portability coverage by rate centre.
- SIP authentication, codec, capacity, fraud-control, and failover requirements.
- SMS/MMS eligibility and API limitations for Canadian DIDs.
- Fixed or nomadic E911 provisioning, address validation, testing, and escalation process.
- STIR/SHAKEN, universal call blocking, CNAM, traceback, and abuse responsibilities.
- Hosted LRN, NPAC/LNP, LERG, routing/rating, and future OCN/SPID support.
- Setup fees, deposits, minimums, recurring fees, usage rates, SLAs, and escalation contacts.
- Reseller, white-label, subaccount, API, and contractual terms.

## Decision boundary

Carrier selection, deposits, account funding, credit commitments, contract acceptance, production routing, number porting, E911 activation, and live traffic require separate user review and authorization.