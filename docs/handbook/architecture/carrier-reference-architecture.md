# WW.CX Carrier Reference Architecture

## Purpose

Define the target technical boundaries for a resilient Canadian voice carrier platform while allowing an incremental partner-assisted launch.

## Architectural principles

1. **Public signaling terminates at an SBC boundary.** Asterisk, FreePBX, customer portals, databases, and management services MUST NOT be directly exposed as the public carrier edge.
2. **Control, media, and management planes are separated.** Administrative access MUST use a restricted management path independent of public SIP signaling.
3. **Every critical function has a documented failure mode.** A component is not production-ready until its loss, timeout, overload behavior, and recovery path are understood.
4. **Configuration is reproducible.** Material configuration MUST be represented by reviewed files, templates, or automation rather than undocumented console-only changes.
5. **Emergency and regulatory functions fail safely.** Routing uncertainty MUST not result in silent misdelivery of emergency calls, number-port requests, or identity assertions.

## Logical layers

### Public edge

- authoritative DNS and service records;
- IPv4 and IPv6 carrier addresses;
- DDoS and network filtering controls;
- primary and secondary session border controllers;
- TLS certificate lifecycle management;
- SIP peer allowlists and rate controls.

### Call-control layer

- routing policy and dial-plan normalization;
- interconnect selection and failover;
- customer and trunk authorization;
- fraud controls;
- STIR/SHAKEN integration;
- number ownership and routing data.

### Media layer

- RTP anchoring where required;
- codec policy;
- DTMF normalization;
- SRTP policy;
- media-quality telemetry;
- geographic and provider diversity where practical.

### Service layer

- customer provisioning;
- billing and rating;
- number inventory and porting workflow;
- emergency-service address workflow;
- support and complaint handling;
- audit and evidence storage.

### Management and evidence layer

- restricted administrative access;
- source control and change review;
- immutable or append-only audit events;
- monitoring, alerting, and incident records;
- backup verification and recovery exercises;
- regulatory evidence register.

## Initial deployment pattern

WW.CX MAY begin with one operational site and an underlying Canadian LEC, provided the arrangement clearly allocates responsibility for numbering, LNP, 9-1-1/NG9-1-1, STIR/SHAKEN, outage escalation, and lawful customer activation. Commercial launch MUST remain gated until single-site and supplier dependencies are accepted or mitigated.

## Target resilient pattern

The target architecture SHOULD provide:

- two independently failure-contained SBC instances;
- redundant upstream interconnect paths;
- redundant authoritative DNS;
- replicated configuration and routing data;
- monitoring from outside the Edge1 failure domain;
- tested backup restoration;
- documented degraded-mode routing;
- an alternate operational access path;
- recovery objectives approved by program leadership.

## Trust boundaries

No service is trusted merely because it is on an internal address. Every interface MUST have an identified owner, authentication method, authorization policy, logging expectation, data classification, and timeout/failure behavior.

## Production-entry criteria

A component may enter production only after:

- configuration review;
- security review proportional to exposure;
- functional and negative testing;
- monitoring and alert ownership;
- backup or reconstruction method;
- rollback procedure;
- evidence location recorded in the carrier obligations register.