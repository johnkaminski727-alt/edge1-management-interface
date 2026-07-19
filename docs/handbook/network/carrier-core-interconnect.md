# Carrier Core and Interconnect Standard

## Purpose

Define how WW.CX designs, qualifies, activates, monitors, changes, and retires carrier interconnects without confusing laboratory readiness with production authorization.

## Architecture boundary

The carrier core MUST separate:

- external carrier and peer signaling;
- session border control and policy enforcement;
- internal SIP routing and PBX services;
- media relay and RTP observability;
- numbering, routing, and portability data;
- customer provisioning and management interfaces;
- operations, audit, and evidence systems.

No external peer may route directly to an internal PBX, application service, database, or management listener.

## Interconnect lifecycle

Every interconnect MUST progress through these states:

1. **Proposed** — business purpose, owner, peer, traffic type, regulatory dependencies, and data handling are recorded.
2. **Designed** — addressing, transports, authentication, codec policy, capacity, routing, monitoring, failure behavior, and rollback are documented.
3. **Lab validated** — synthetic traffic proves signaling, media, failure handling, observability, and isolation.
4. **Non-production pilot** — an approved limited test confirms interoperability using controlled identifiers and explicit stop conditions.
5. **Production authorized** — commercial, legal, regulatory, security, emergency-service, and operational gates are complete.
6. **Active** — the peer is monitored against agreed service objectives and change control.
7. **Suspended or retired** — traffic is removed deliberately, evidence is retained, dependencies are closed, and credentials are revoked through an approved process.

A lower state MUST NOT be represented as production-ready.

## Peer profile

Maintain a peer profile containing at minimum:

- accountable owner and escalation contacts;
- legal and commercial relationship reference;
- signaling addresses and permitted transports;
- certificate or authentication method references, never embedded secrets;
- accepted source and destination identities;
- permitted traffic classes and direction;
- codec, DTMF, fax, and media policy;
- SIP timers, session refresh, and retry behavior;
- routing precedence and failover order;
- capacity assumptions and protective limits;
- test cases, evidence locations, and last review date;
- emergency-calling, lawful-intercept, privacy, and recording applicability where relevant.

## Routing discipline

- Routing MUST be explicit, deterministic, and deny by default.
- Number normalization MUST occur before policy and route selection.
- Test ranges, service numbers, emergency destinations, and administrative codes MUST be handled by dedicated policy.
- Route changes MUST include expected impact, validation queries, rollback, and post-change evidence.
- Automatic failover MUST not silently move traffic to a path lacking equivalent emergency-service, identity, privacy, or compliance capability.
- Synthetic or placeholder carrier data MUST be visibly marked and MUST NOT appear as live operational truth.

## Signaling and media controls

- Prefer encrypted signaling and media where supported and approved.
- Validate certificate identity, trust chain, expiry, and revocation posture.
- Enforce topology hiding, malformed-message limits, rate limits, and transaction limits at the SBC boundary.
- Restrict media to approved relay paths and expected address ranges.
- Reject unsupported codecs and unexpected media renegotiation according to peer policy.
- Capture diagnostics with privacy-safe retention; do not place customer content or credentials in routine logs.

## Capacity and resilience

Capacity planning MUST account for concurrent calls, calls per second, registration volume, media bandwidth, transcoding cost, signaling bursts, retry storms, and maintenance headroom. Each production peer SHOULD have a tested failure mode and, where required, a diverse alternate path. Diversity claims require evidence that the paths do not share an unrecognized carrier, facility, power, DNS, certificate, or administrative dependency.

## Monitoring

Monitor at minimum:

- peer reachability and SIP OPTIONS results;
- registration or trunk state where applicable;
- attempts, answers, failures, and release causes;
- post-dial delay and answer-seizure ratio;
- RTP loss, jitter, latency, and one-way-media indicators;
- certificate expiry and trust failures;
- route utilization and capacity thresholds;
- abnormal retries, scans, fraud indicators, and policy denials.

Alerts MUST identify the affected peer, traffic direction, observed symptom, likely customer impact, and the runbook to use.

## Activation checklist

Production activation requires recorded confirmation of:

- approved design and peer profile;
- completed security review;
- successful interoperability and failure tests;
- monitoring and alert ownership;
- capacity and resilience review;
- emergency-service and numbering dependencies where applicable;
- change record, maintenance window, communications plan, and rollback;
- commercial and regulatory authority;
- post-activation validation plan.

## Rollback

Rollback MUST restore the last known safe route and policy state, verify signaling and media, confirm emergency-routing posture where applicable, and preserve logs and configuration evidence. Do not destroy diagnostic evidence during rollback.