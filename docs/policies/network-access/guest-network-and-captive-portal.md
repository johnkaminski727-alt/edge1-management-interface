# Proposed Guest Network & Captive Portal Terms

Status: **DRAFT / NOT ACTIVE**  
Audience: visitors and other users who are not being granted WW.CX private-network access  
Acceptance: proposed click-through captive-portal acceptance per guest session

## Separate service

The guest network should be a distinct, internet-only service. Accepting guest terms must not create a private-network device registration, a WireGuard credential, or access to WW.CX management, server, storage, printer, telephony, or other internal resources.

## Proposed access model

The default guest experience should be simple:

1. join the designated guest wireless network;
2. receive an address on the isolated guest segment;
3. see the captive portal;
4. review the current guest terms and privacy summary;
5. accept the displayed policy version;
6. receive a time-limited internet-access session.

Ordinary guest access should not require a WW.CX account when anonymous click-through access is sufficient. Voucher or sponsor access may be offered for events, contractors, longer stays, or higher-trust use cases.

## Proposed acceptable use

Guests may use the service for ordinary lawful internet access. Guests must not knowingly:

- attempt to access WW.CX private systems or bypass guest isolation;
- attack, scan, interfere with, or compromise other users, systems, or networks;
- distribute malware, conduct denial-of-service activity, send abusive bulk traffic, or perform credential attacks;
- impersonate another user or deliberately evade session, rate, or security controls;
- operate a public relay, proxy, or exit service from the guest connection;
- use the service for activity that is unlawful or materially interferes with service for others.

Authorized event demonstrations or security testing require an explicitly approved scope rather than relying on ordinary guest access.

## Privacy summary

The preferred guest design collects only what is reasonably necessary to create and operate the guest session. This may include a random session identifier, accepted policy version, start/expiry time, assigned network address, limited usage counters, and a pseudonymous device handle if required by the access controller.

Ordinary guest access should not collect browsing history or inspect encrypted content as a standard condition of access. WW.CX should not perform TLS interception for captive-portal enforcement.

Voucher or sponsor information should be collected only when that access mode is used.

## Proposed session limits

Initial engineering defaults for review:

- session lifetime: **12 hours**;
- idle timeout: **60 minutes**;
- reconnect grace: **15 minutes** where the controller can safely recognize the same session;
- bandwidth: reasonable per-client rate limits rather than an unrestricted shared uplink.

These values are operational proposals, not approved commitments, and should be configurable.

## Security limitations

A guest Wi-Fi network is an untrusted network. Users should prefer encrypted applications and HTTPS. Client isolation should prevent direct guest-to-guest communication where supported, but WW.CX should not represent the guest service as protecting a user's device from every internet or endpoint threat.

## Availability and suspension

Guest access may be limited, rate-limited, suspended, or terminated for maintenance, capacity, abuse, security, policy expiry, or upstream-service reasons. The service is not intended as a substitute for private WW.CX access.

## Policy changes

A material guest-policy change should create a new `guest-*` policy version. A new guest session should accept the currently active guest version; previous private/VPN policy acceptance must not satisfy guest acceptance, and guest acceptance must not satisfy private/VPN requirements.

## Activation boundary

This proposal does not create a guest SSID, VLAN, DHCP scope, DNS policy, firewall rule, captive redirect, authentication service, or internet route. Those changes require a separately reviewed and explicitly authorized deployment.