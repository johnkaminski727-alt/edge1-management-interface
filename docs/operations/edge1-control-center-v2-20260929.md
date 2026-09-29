# Edge1 Control Center v2 — reviewed implementation proposal

Date: 2026-09-29

## Decision

The existing registry-driven Operator Shell remains the correct foundation. It already provides the essential synchronized-navigation contract: one canonical module registry feeds desktop navigation, mobile navigation, the jump palette and ToolBox without turning navigation metadata into authorization.

The next interface generation builds on that contract rather than replacing it.

## Required experience

The authenticated Edge1 landing experience is a comprehensive control center, not a single-purpose Security Console. It must summarize and link the major operational domains:

- system and service health;
- firewall and security posture;
- CrowdSec and PASS/ASE;
- network interfaces and routing;
- WireGuard/private access;
- DNS, AdGuard, filtering and split DNS;
- running/candidate configuration and pending changes;
- validation, apply jobs, checkpoints and rollback;
- Contacts & Relationship Management;
- AVA agent status, tasks, approvals and connectors;
- audit/history and operator evidence;
- contextual ToolBox actions.

Healthy systems should remain compact. Attention states, failed services, pending changes, sanctions, AVA approvals and relationship-review work should rise in prominence.

## Synchronized navigation model

The canonical source remains:

`config/edge1_operator/navigation_registry.json`

The same registry now drives or declares:

- desktop menu;
- mobile drawer;
- dashboard module inventory;
- jump/search palette;
- ToolBox eligibility;
- live/upcoming module badges;
- module descriptions and section grouping.

A module is registered once. Browser navigation is still fail-closed: only `accepted_live` entries with an accepted rooted `browser_route` become links. Upcoming modules may be visible as disabled status rows, but visibility never grants authority and does not invent a route.

## Information architecture

Primary groups:

1. **Operations**
   - Control Center
   - Release/operations status
2. **Security**
   - Security Operations
   - Firewall
   - Security Correlation
   - CrowdSec
   - PASS/ASE
3. **Network**
   - Network & DNS Defense
   - WireGuard & VPN
   - DNS & Filtering
4. **Intelligence**
   - Contacts & Relationships
   - Communications intelligence
5. **AI & Automation**
   - AVA
   - approved automation surfaces
6. **Configuration**
   - Changes & Apply
   - Audit & History
7. **Tools**
   - specialist modules such as Cookie Monster when separately accepted

## Contacts & Relationship Management

The current Unified Contacts implementation is not discarded. It becomes the Contacts & Relationships specialist console under the shared Edge1 shell. Its identity/provenance separation and relationship/correlation model remain authoritative.

The browser route is not promoted solely because source files exist. Route acceptance and authenticated private-ingress integration remain separate gates.

## AVA

AVA is a first-class Edge1 module. The repository already contains bounded agent-controller, operator-broker and gateway components. The UI integration must expose status, tasks, approvals, connector health and recent agent activity without granting new scopes merely because a menu item is visible.

Unrestricted shell gates remain separate, explicit and disabled by default unless their existing authorization model says otherwise.

## Security and network integration

Firewall, VPN and DNS are not buried inside a generic Security card. The landing page must present separate operational signals for:

- firewall posture/exposure;
- CrowdSec/bouncer;
- PASS/ASE;
- authentication/session health;
- certificate/TLS health;
- WireGuard/private access;
- AdGuard/DNS health and split DNS;
- recent security events.

## Authentication boundary

The Business159 assertion -> Edge1 opaque-session model remains authoritative.

The current authenticated Security Console proves the trust path. Control Center v2 reuses that session model and does not weaken it. Route publication must preserve:

- private WireGuard-only HTTPS ingress;
- server-side authorization;
- secure opaque session cookies;
- CSRF protection for authenticated POST;
- mutation-denial by default;
- direct-route authorization;
- no browser exposure of service secrets.

## Current implementation step

This branch introduces the v2 registry metadata, grouped synchronized navigation, comprehensive Control Center content, Contacts shell integration, and AVA/Contacts/Firewall/VPN/DNS/Changes/Audit module registration.

Modules without an accepted authenticated browser path remain visible only as upcoming/private status and are not clickable.

## Remaining route-integration work

The current private nginx ingress exposes the authenticated `/edge1-ops/` namespace. Several historical read-only pages still live under `/edge1-status/`, and Contacts currently has its own runtime route.

Do not solve that gap by weakening cookie scope or bypassing application authorization.

The next route-integration phase should place accepted specialist pages behind the authenticated private ingress, with one coherent namespace and explicit direct-route tests, then promote their registry entries only after browser acceptance.

## Acceptance criteria

- authenticated Control Center loads through `https://edge1.ww.cx`;
- synchronized navigation comes from the canonical registry;
- desktop/mobile/palette/dashboard stay consistent;
- upcoming AVA and Contacts modules are represented without premature route promotion;
- firewall/security/network/VPN/DNS are first-class dashboard domains;
- direct-route authorization remains fail-closed;
- mutations remain denied unless a separately approved action explicitly enables them;
- no public HTTPS listener is introduced;
- tests and publisher validation pass;
- deployment retains rollback evidence.
