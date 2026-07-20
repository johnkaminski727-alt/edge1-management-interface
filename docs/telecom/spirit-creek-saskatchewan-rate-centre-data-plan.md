# Spirit Creek Communications — Saskatchewan Rate-Centre Data Plan

**Status:** Design ready; provider inventory pending  
**Last updated:** 2026-07-20

## Objective

Create a canonical, evidence-backed dataset that can support internal carrier selection and, later, a customer-facing Saskatchewan number-availability workflow without presenting unverified inventory as available.

## Data layers

Keep these layers separate:

1. **Geographic reference:** community, province, coordinates or service area, and recognized aliases.
2. **Numbering reference:** NPA, NXX, rate centre, LATA or Canadian equivalent data where applicable, and source/effective date.
3. **Carrier capability:** provider-stated support for DID ordering, porting, SMS/MMS, E911, toll-free, and SIP.
4. **Inventory observation:** dated portal/API/manual observation of orderable numbers.
5. **Commercial eligibility:** account, reseller, minimum, and contract constraints.
6. **Customer eligibility:** service address, emergency-service requirements, porting evidence, and intended use.

An inventory observation is time-sensitive and must never be treated as a guaranteed reservation.

## Proposed schema

| Field | Description |
|---|---|
| `country_code` | `CA` |
| `province_code` | `SK` |
| `community_name` | Canonical community name |
| `community_aliases` | Alternate names used in provider portals or source material |
| `rate_centre_name` | Source-exact rate-centre label |
| `npa` | Three-digit numbering-plan area |
| `nxx` | Optional prefix when supported by authoritative data |
| `provider` | Carrier or hosted-number provider |
| `service_type` | DID, porting, toll-free, SMS, MMS, E911, SIP |
| `evidence_state` | verified, provider-stated, observed, pending, unavailable |
| `inventory_count_observed` | Optional count at observation time; never guaranteed |
| `observed_at` | UTC timestamp |
| `source_reference` | Sanitized evidence identifier or public source |
| `effective_date` | Source effective date where available |
| `restrictions` | Address, account, documentation, usage, or portability constraints |
| `notes` | Non-sensitive qualification notes |

## Initial priority communities

Start with the communities already requested in carrier correspondence:

- Regina
- Saskatoon
- Yorkton
- Invermay and nearby eastern Saskatchewan communities

Expansion should follow customer demand and verified provider coverage rather than assumptions.

## Collection workflow

1. Import authoritative public numbering and geographic reference data under documented licensing terms.
2. Normalize rate-centre and community names while retaining source-exact values.
3. Collect written provider coverage statements.
4. Observe inventory only through an authorized portal or API and record the observation timestamp.
5. Reconcile conflicts by retaining both evidence records and marking the customer-facing result pending.
6. Validate that no credentials, account URLs, customer addresses, or reserved telephone numbers enter the repository.
7. Publish only availability classes such as `likely available`, `provider confirmation required`, or `not currently observed`; never promise a number before reservation.

## Customer-facing availability states

- `reference coverage`: the rate centre exists in the canonical reference dataset.
- `provider-stated coverage`: a provider says it serves the area, but inventory has not been observed.
- `inventory observed`: numbers were visible at a recorded time, subject to change.
- `portability review required`: a number may be portable only after provider validation.
- `unavailable`: provider or authoritative evidence states the service is not offered.
- `unknown`: evidence is insufficient.

## Validation requirements

- Unique source/effective-date history for every record.
- Deterministic normalization tests for province, community, NPA, and rate-centre names.
- Duplicate detection across providers and observations.
- Freshness warnings for inventory observations.
- Explicit separation between public reference data and private carrier/account evidence.

## Blockers

Provider-specific Saskatchewan inventory, API access, commercial permission, and authoritative licensing review remain pending. No live inventory collection or customer-facing publication is authorized by this plan.