# WW.CX Engineering & Carrier Handbook

**Edition:** 1.0 working public edition  
**Status:** Active engineering and operations reference  
**Owner:** WW.CX carrier program

This handbook translates the WW.CX Canadian Carrier Readiness Roadmap into durable engineering, operations, security, and governance standards for Edge1 and future carrier infrastructure.

> This handbook is an implementation reference, not legal advice. Regulatory requirements must be validated against current primary sources, applicable agreements, and qualified Canadian telecommunications counsel.

## Core documents

- [Carrier reference architecture](architecture/carrier-reference-architecture.md)
- [SIP and SBC engineering standard](network/sip-sbc-standard.md)
- [Operational readiness standard](operations/operational-readiness.md)
- [Monitoring and incident response](operations/monitoring-incident-response.md)
- [Security baseline](security/carrier-security-baseline.md)
- [Disaster recovery standard](resilience/disaster-recovery.md)
- [Evidence management standard](governance/evidence-management.md)

## Relationship to the carrier program

The handbook supports the documents under [`docs/carrier/`](../carrier/README.md). The carrier program defines what must be achieved; this handbook defines how WW.CX intends to design, operate, secure, validate, and preserve evidence for the resulting platform.

## Mandatory language

- **MUST** indicates a required control.
- **SHOULD** indicates a strong recommendation that requires a documented exception if not followed.
- **MAY** indicates an optional implementation choice.

## Change discipline

Material changes to public routing, production SIP behavior, emergency calling, numbering, security boundaries, certificates, firewall policy, or customer-impacting systems MUST use a reviewed change record with validation and rollback steps.