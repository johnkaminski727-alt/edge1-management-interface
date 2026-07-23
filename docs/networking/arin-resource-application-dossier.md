# ARIN Resource Application Dossier

**Status:** Pre-application working record  
**Last updated:** 2026-07-23  
**Scope:** Prepare Spirit Creek Gardens Inc. for an ARIN Org ID, ASN, IPv6 request, and an IPv4 waiting-list or transfer-recipient qualification request.

## Verified organization identity

- Legal name: Spirit Creek Gardens Inc.
- Federal corporation number: 1651475-8
- Operating initiatives: Spirit Creek Communications and WW.CX
- Mailing address: PO Box 333, Invermay, Saskatchewan S0A 1M0, Canada
- Authorized representative: John W. Kaminski
- Contact email: johnkaminski727@gmail.com
- Contact telephone: +1 306-383-7061

Do not store a CRA Business Number, account credentials, private activation links, identity documents, signatures, payment data, or ARIN authentication material in this repository.

## Intended network purpose

Spirit Creek Gardens Inc. is preparing an independently administered Canadian Internet and telecommunications network. The intended architecture includes:

- external BGP relationships with more than one upstream and/or peering partner;
- independent IPv4 and IPv6 routing policy;
- regional Internet-exchange and remote-peering participation;
- authoritative and public infrastructure hosted independently of a single access provider;
- RPKI Route Origin Authorizations and IRR route objects;
- documented prefix filtering, maximum-prefix controls, routing security, monitoring, and rollback;
- separation between Internet routing, telephony signaling, management, and customer-facing services.

No statement in this dossier claims that multihoming, public BGP announcements, carrier interconnection, production traffic, or Internet-exchange membership is already active.

## Proposed ASN justification

Spirit Creek Gardens Inc. requires a globally unique autonomous system number to operate an independent routing policy across multiple planned external BGP relationships. The ASN will support IPv6 deployment, future provider-independent IPv4 resources or transferred IPv4 resources, Internet-exchange participation, RPKI and IRR publication, and controlled routing between independently administered infrastructure and upstream or peering partners.

The deployment is being developed in stages. Provider and exchange inquiries are non-binding and no live BGP session will be activated until addressing, filtering, routing-security, contractual, and operational controls are approved.

## Planned external relationships

Current candidates and inquiry status:

| Candidate | Relationship under evaluation | Status |
|---|---|---|
| ARIN | Org ID, ASN, IPv6, IPv4 policy guidance | Preliminary inquiry sent |
| IXP.MX / CITI | Internet-exchange membership or remote peering | Preliminary inquiry sent |
| ThinkTel | Canadian SIP, DID, and wholesale carrier services | Technical follow-up sent |
| VoIP.ms | Saskatchewan DID inventory and SIP qualification | Inventory inquiry sent |
| Additional Canadian transit providers | IPv4/IPv6 transit and BGP | To be identified |
| Additional remote-peering providers | Transport to regional IXPs | To be identified |

A provider inquiry is not proof of an available service, accepted order, active circuit, or BGP relationship.

## Org ID and POC preparation

The authenticated ARIN Online workflow must be completed by the authorized representative.

Expected records:

- Individual ARIN Online account for John W. Kaminski.
- Individual POC linked to the account.
- Organization Identifier for Spirit Creek Gardens Inc.
- Administrative POC.
- Technical POC.
- NOC POC.
- Abuse POC.

Before submission, confirm whether ARIN permits the same verified person and address to fill more than one role during initial formation. Create role-specific email aliases only after the corresponding mailboxes are operational and monitored.

## Supporting evidence checklist

Prepare outside the repository:

- federal certificate or current corporate profile for corporation 1651475-8;
- evidence linking John W. Kaminski to the corporation and authority to act;
- registered-office evidence if requested;
- mailing-address evidence if requested;
- network diagram and implementation timeline;
- candidate upstream and peering correspondence;
- router and facility descriptions;
- IPv6 addressing and utilization plan;
- IPv4 utilization plan;
- service and customer growth assumptions, clearly labeled as forecasts;
- technical contact and escalation procedures.

## IPv6 request planning

Preferred approach:

1. Obtain the Org ID and ASN.
2. Confirm the smallest suitable provider-independent IPv6 allocation under current ARIN policy.
3. Document hierarchical allocation for infrastructure, loopbacks, point-to-point links, management, services, and future sites.
4. Create RPKI and IRR records before public route activation.
5. Announce only aggregate prefixes that comply with accepted global filtering practice.

The final prefix size must be justified under current ARIN policy and must not be invented in advance.

## IPv4 request planning

ARIN's ordinary IPv4 free pool is exhausted. The working paths are:

- IPv4 Waiting List eligibility, subject to current policy and availability;
- specified-recipient transfer qualification under applicable ARIN policy;
- provider-assigned space as a transitional option;
- any policy-specific pool for which the network can truthfully qualify.

The anticipated use is dual-stack edge infrastructure, authoritative services, carrier and exchange interconnection, management endpoints requiring public reachability, and independently routed public services.

Do not claim utilization that does not exist. Forecasts must identify the service, address count, deployment date, and technical reason public IPv4 is required.

## Xpressnet historical-resource inquiry

ARIN has been asked for guidance on resources historically associated with an Edmonton-area provider known as Xpressnet or XpressNet.

Current limits:

- no exact Org ID, ASN, or netblock has been verified;
- Spirit Creek Gardens Inc. is not asserting ownership or transfer rights;
- historical registration does not imply availability;
- any transfer would require current registrant authority, ARIN approval, recipient qualification, agreements, and payment.

Record exact identifiers only after verification through ARIN RDAP/Whois or a Registration Services response.

## Formal submission boundaries

The engineering agent may prepare evidence, drafts, diagrams, repository records, and technical responses. The authorized representative must personally handle:

- ARIN Online authentication and identity verification;
- submission of sensitive corporate or tax identifiers;
- certifications and declarations;
- acceptance or signature of the Registration Services Agreement;
- invoices and payments;
- acquisition or transfer agreements;
- authorization of live route announcements.

## Proposed application answers

### Description of organization

Spirit Creek Gardens Inc. is a federally incorporated Canadian organization developing Spirit Creek Communications and WW.CX, an independently administered Internet and telecommunications infrastructure initiative based in Saskatchewan.

### Reason for requesting an ASN

The organization plans to establish external BGP relationships with multiple independently administered upstream and peering networks. A unique ASN is required to express its own routing policy, originate its IPv6 and future IPv4 prefixes, participate in Internet exchanges, and publish RPKI and IRR routing-security records.

### Deployment timeline

The implementation is staged. Organization and resource registration, addressing, routing policy, lab validation, upstream qualification, and security controls will precede any production announcement. Specific activation dates depend on ARIN approval and provider readiness and must not be represented as guaranteed.

### Routing-security controls

The network will implement explicit import and export filters, maximum-prefix limits, bogon filtering, RPKI origin validation where supported, IRR-based filters, conservative default routing, peer-specific policy, monitored sessions, and documented rollback.

## Completion gates

The dossier is ready for formal use when:

- ARIN replies to the pre-application questions;
- the ARIN Online account and POC are created;
- the Org ID is validated;
- corporate evidence has been gathered privately;
- the network plan and addressing forecast are reviewed;
- at least two plausible external BGP relationships are documented;
- the authorized representative approves any certification, agreement, or fee.