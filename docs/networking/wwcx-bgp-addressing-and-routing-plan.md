# WW.CX BGP, Addressing, and Routing Plan

**Status:** Pre-production design  
**Last updated:** 2026-07-23  
**Scope:** Define the minimum safe architecture required before Spirit Creek Gardens Inc. activates an independently routed ASN, IPv6 space, or transferred/wait-listed IPv4 space.

## Design goals

- Operate a distinct routing policy under a unique ASN.
- Support at least two independently administered external BGP relationships.
- Prefer IPv6-first deployment while preserving justified dual-stack services.
- Keep routing, telephony, management, and customer-facing services logically separated.
- Publish only verified prefixes with matching RPKI and IRR records.
- Prevent route leaks, excessive advertisements, accidental transit, and unauthorized origination.
- Permit staged lab testing and rapid rollback before production activation.

## Initial topology

The first independently routed site is expected to use Edge1 as the monitored service and control environment, but the final production border-router role must be assigned only after hardware, virtualization, kernel forwarding, redundancy, and upstream requirements are validated.

Proposed logical components:

1. Border routing plane
   - one or two BGP-capable routers;
   - separate peer sessions per upstream or exchange;
   - no default transit between peers unless explicitly contracted and configured;
   - route-policy configuration stored and reviewed separately from secrets.

2. Infrastructure network
   - router loopbacks;
   - DNS, monitoring, NTP, status, and management services;
   - authoritative infrastructure where independently routed addressing is operationally justified.

3. Service network
   - WW.CX public services;
   - carrier and telephony control endpoints;
   - future customer-facing services;
   - no assumption that every service requires a dedicated public IPv4 address.

4. Management network
   - private addressing by default;
   - access through authenticated management paths;
   - no direct public exposure unless separately reviewed.

## External BGP relationships

A formal ASN request should describe planned relationships truthfully and avoid claiming active sessions.

Minimum target:

- External relationship A: Canadian IPv4/IPv6 transit provider.
- External relationship B: second transit provider, remote-peering service, or Internet-exchange route-server/member relationship.

Candidate discussions may be listed as planned or under evaluation only.

## Import policy

Each external session should implement:

- explicit accepted address families;
- maximum-prefix limits with warning and shutdown thresholds;
- rejection of default routes unless intentionally accepted from a transit provider;
- rejection of bogons, martians, own prefixes, and invalid-length announcements;
- RPKI origin validation where supported;
- IRR-derived filters where reliable;
- peer-specific local preference;
- conservative handling of unknown communities;
- logging and alerting for session and route-count changes.

## Export policy

Export only:

- prefixes registered to or validly delegated to Spirit Creek Gardens Inc.;
- prefixes authorized by current ROAs;
- prefixes covered by matching IRR route or route6 objects where required;
- aggregates that meet the receiving network's minimum-prefix policy;
- no third-party routes unless a separately authorized transit service exists.

Never export:

- RFC1918, ULA, link-local, documentation, benchmark, multicast, or reserved ranges;
- more-specific routes not explicitly approved;
- routes learned from one peer to another unless intentional transit is contracted;
- stale or transferred-away prefixes.

## IPv6 plan

The exact provider-independent allocation size must be determined under current ARIN policy. Once allocated, use a hierarchical plan with reserved growth.

Suggested functional hierarchy:

- border-router loopbacks;
- point-to-point and interconnect links;
- infrastructure services;
- management systems;
- telephony and carrier-control services;
- public application services;
- lab and validation environments;
- future facilities and customer assignments, only where policy permits.

Operational rules:

- use stable addressing plans rather than embedding host identity assumptions;
- aggregate announcements whenever possible;
- filter router advertisements and DHCPv6 by segment role;
- use ULA only for internal functions where global addressing is unnecessary;
- avoid NAT66 as a substitute for routing policy;
- document reverse DNS delegation before production service activation.

## IPv4 plan

Public IPv4 must be justified per service and deployment date.

Prefer, in order:

1. provider-independent resources obtained through an ARIN-approved path;
2. transferred resources after recipient qualification and due diligence;
3. provider-assigned addresses for transitional connectivity;
4. shared or proxied service designs where dedicated addresses are unnecessary.

Initial categories that may require public IPv4:

- border and upstream interconnection endpoints where required by the provider;
- authoritative infrastructure that cannot yet operate IPv6-only;
- carrier or SIP control endpoints requiring fixed public source addresses;
- externally reachable services that cannot be placed behind a reverse proxy or shared ingress;
- monitoring endpoints required by an upstream or exchange.

Do not request addresses for dormant, speculative, duplicate, or NAT-capable internal systems without a documented technical reason.

## RPKI and IRR

Before announcing any prefix:

- create a ROA for the authorized origin ASN;
- use the narrowest reasonable maxLength;
- create matching IRR route/route6 objects where required;
- verify public visibility through independent validators;
- document renewal and key/account recovery procedures;
- ensure stale authorizations are removed promptly after topology or ownership changes.

## PeeringDB readiness

After ASN issuance and before exchange participation:

- create the organization record using the exact legal entity;
- create the network record for the issued ASN;
- publish accurate NOC and policy contacts;
- describe IPv4 and IPv6 capability truthfully;
- publish facilities and exchanges only after service is ordered or active;
- do not publish private credentials, circuit IDs, or unverified capacity.

## Lab validation

Before any public BGP activation, validate with isolated or documentation-only peers:

- configuration syntax;
- prefix-list and route-map behavior;
- maximum-prefix shutdown and recovery;
- rejection of own-prefix and default-route leaks;
- RPKI valid, invalid, and unknown handling;
- graceful restart behavior;
- session flap alerting;
- configuration rollback;
- service reachability through each intended path;
- no unintended transit between peers.

## Production activation gates

Public BGP may proceed only after:

- ASN and address resources are issued or validly delegated;
- upstream or exchange agreements are approved;
- fees are separately authorized and paid;
- router configuration is peer reviewed;
- ROAs and IRR records are published;
- prefix and maximum-prefix filters are confirmed by both sides;
- monitoring and rollback are operational;
- an activation window and responsible contacts are agreed;
- the user explicitly authorizes live route activation.

## Rollback principle

Every activation must have a bounded rollback that can:

- administratively disable the new BGP session;
- withdraw only the newly introduced prefixes;
- restore the prior provider-assigned path if one exists;
- preserve management access;
- capture logs and route tables for analysis;
- avoid unrelated DNS, firewall, telephony, or application changes.