# Proposed WW.CX Network Access Policy Set

Status: **DRAFT / PROPOSED ONLY**  
Activation authorized: **no**  
Legal/privacy review required before publication or acceptance: **yes**

These documents are working policy proposals for the WW.CX private network, Edge1 VPN, and a future guest network. They are intentionally not active policy text and are not accepted on behalf of any user.

## Proposed policy set

1. [Network Access & Acceptable Use](network-access-and-acceptable-use.md) — baseline rules for account-owned private-network and VPN access.
2. [Privacy, Security Monitoring & Logging Notice](privacy-security-monitoring-and-logging.md) — data-minimization, operational logging, security-event, and retention proposal.
3. [Device Registration & Credential Lifecycle](device-registration-and-credential-lifecycle.md) — account ownership, enrollment, replacement, revocation, and lost-device handling.
4. [Network Enforcement, Quarantine & Incident Response](network-enforcement-and-incident-response.md) — proposed status model, quarantine rules, exemptions, and audit requirements.
5. [Guest Network & Captive Portal Terms](guest-network-and-captive-portal.md) — separate internet-only guest access and captive-portal consent proposal.

The proposed guest network architecture is described separately in [Guest Captive Portal Architecture](../../guest-captive-portal-architecture.md).

## Policy design principles

- **Account ownership is stable.** Private/VPN devices are owned by the signed WW.CX subject (`wwcx-user-<id>`), not by a display name or mutable username.
- **Guest access is separate.** Guest sessions must not become private-network device registrations and must not inherit VPN/private-network trust.
- **Data minimization is the default.** Do not inspect payload content, intercept TLS, or collect browsing history as a normal condition of access.
- **Explicit consent is versioned.** Any policy that requires acceptance is versioned, displayed before acceptance, and recorded with time, policy version, subject/session, and source.
- **No silent policy acceptance.** Administrators do not accept a user-facing policy on behalf of the user except for an explicitly documented non-user service exemption.
- **Enforcement is a separate activation.** Draft policies may be merged and reviewed without enabling firewall, DNS, proxy, captive portal, or VPN enforcement.
- **Privacy and security controls apply equally to IPv4 and IPv6.** A guest or private-network boundary is incomplete if only one protocol family is isolated.

## Proposed versioning

The first reviewed private-network bundle should receive a stable version such as `network-2026-01` only after legal/privacy review. The guest policy should use its own namespace, for example `guest-2026-01`, so guest acceptance never satisfies private/VPN acceptance.

The current VPN registration pilot remains enforcement-inactive until an approved policy version is deliberately activated.