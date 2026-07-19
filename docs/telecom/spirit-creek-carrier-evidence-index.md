# Spirit Creek Communications — Carrier and Numbering Evidence Index

**Status:** Active / archive-ready snapshot  
**Last updated:** 2026-07-19

This index identifies evidence locations without storing credentials, private activation links, tokens, account URLs, or other secrets.

## Identity and readiness

| Evidence | Location | Verified fact | Limitation |
|---|---|---|---|
| Numbering-readiness register | `docs/telecom/spirit-creek-communications-numbering-readiness.md` | Spirit Creek Communications is the working applicant identity; Canada-incorporated status and Invermay address are recorded | Exact legal corporate name, applicant corporation number, and operating-name relationship remain pending |
| Readiness documentation PR | GitHub PR #21; merge commit `dd4e6042af8c16bcf8ff68c3b606b8f02babf836` | Readiness documentation merged to `main` | Repository documentation is not regulatory approval |
| Execution queue | GitHub Issue #24 | Authoritative pending-work checklist and safety boundaries | Checklist status must be updated as evidence changes |

## Interconnect engineering

| Evidence | Location | Verified fact | Limitation |
|---|---|---|---|
| Staged interconnect PR | GitHub PR #16 | Merged; PR record states `WW.CX interconnect staging validation` and repository validation passed on head `2259a9871c13ab827f6793fc8fd4ea94d721558f` | Staging validation does not authorize production traffic or carrier activation |
| Interconnect workflow | `.github/workflows/wwcx-interconnect-staging.yml` | Staged validation covers assets, numbering-node tests, and source lifecycle | Does not activate live SIP, routing, trunks, firewall, DNS, certificates, E911, or traffic |

## Gmail correspondence

Gmail message IDs and private URLs are intentionally not copied into repository records. Search by the following stable references:

| Organization | Search reference | Current classification | Material evidence |
|---|---|---|---|
| VoIP.ms | Sales thread `B9ZWS8`; support tickets `N61QEU`, `B78N34`, `NFX94W` | Provider capability statement, verified account activation, onboarding follow-up sent, plus automated ticket notices | Asterisk/FreePBX support; Canadian DIDs in many rate centres; local portability subject to eligibility; SMS API; MMS on supported numbers; E911 on eligible DIDs; reseller program; Saskatchewan onboarding dataset requested |
| VoIP.ms | Subjects `Activate your account` and `Welcome to VoIP.ms` from VoIP.ms | Activation completed and verified | User completed the private activation workflow; welcome message received on 2026-07-19; private URLs excluded |
| ThinkTel | `CT-12603061-6A1F / 12603061` | Automated acknowledgement and request echo | No pricing, coverage, technical acceptance, or commercial terms |
| ThinkTel | `CT-12603062-C1F7 / 12603062` | Automated acknowledgement and request echo | No pricing, coverage, technical acceptance, or commercial terms |
| Canadian Numbering Administrator | `COCodeApps@cnac.ca`; subjects containing `Thousands-Block` or `Spirit Creek Communications` | Inquiry and identity correction sent | No substantive response located as of 2026-07-19 |
| CRTC | `cd-dc@crtc.gc.ca`; subject containing `Telecommunications Provider Registration Guidance` | Guidance inquiry sent | No substantive response located as of 2026-07-19 |
| Iristel | `wholesale@iristel.com` | Inquiry sent | No substantive response located as of 2026-07-19 |
| ISP Telecom | `sales@isptelecom.net` | Inquiry sent | No substantive response located as of 2026-07-19 |

## Public primary sources

| Source | Use | Current verified requirement |
|---|---|---|
| CRTC telecommunications-provider registration pages | Registration planning | Organizations offering telecommunications services in Canada generally must register; reseller status depends on the service and facilities model |
| CRTC registration application instructions | Unsigned application preparation | Application letter requires legal name, contact data, response manager, services, legal structure, facilities statement, requested registration list, and compliance acknowledgement |
| CRTC local VoIP 9-1-1 obligations | E911 dependency package | Local VoIP providers must address 9-1-1 service, customer limitation notifications, registration status, and BITS where applicable |
| CRTC BITS information | International-traffic dependency | A BITS licence is required if the provider carries telecommunications traffic internationally; application includes a signed and notarized affidavit |

## Unresolved documentary requirements

- Exact legal corporate name of the applicant.
- Applicant corporation number.
- Documentary relationship between Spirit Creek Communications and Spirit Creek Gardens Inc.
- Operating-name registration or authority.
- CRTC registration category and confirmation.
- BITS applicability and, if required, licence.
- Hosted carrier agreement and carrier identifiers.
- OCN, NPAC SPID, LRN, switch/CLLI, LIR status, and routing/rating data.
- E911 provider and approved customer notification materials.
- Initial Saskatchewan rate centre and NPA.
- Executed CNA/CNAC Service User Agreement and current application forms.
- Written carrier answers for Saskatchewan inventory, pricing, minimums, reseller terms, SLAs, escalation, and hosted numbering support.

## Evidence handling rules

- Ticket creation is not carrier acceptance.
- Provider capability statements are not inventory confirmations.
- Account activation is not carrier approval, service availability, or acceptance of commercial terms.
- Draft applications are not filings.
- Do not store activation links, credentials, private tokens, or sensitive account URLs.
- Record signatures, certifications, payments, regulatory submissions, and production changes only after separate verified action.
