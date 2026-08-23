# Proposed Privacy, Security Monitoring & Logging Notice

Status: **DRAFT / NOT ACTIVE**  
Audience: private/VPN users and, where stated, guest users  
Legal/privacy review required: **yes**

## Objective

Operate WW.CX network services with the minimum data reasonably needed for authentication, routing, troubleshooting, abuse prevention, security response, and policy compliance.

## Proposed baseline data

For account-owned private/VPN devices, WW.CX may maintain:

- the stable WW.CX account subject associated with the device;
- device display name and assigned network address;
- a one-way fingerprint of the WireGuard public key rather than the raw public key in registration records;
- device enrollment, revocation, quarantine, and policy-acceptance timestamps;
- active policy version and acceptance status;
- recent operational observation timestamps and limited health/state information;
- security or administrative audit events needed to explain access decisions.

For guest sessions, the preferred baseline is a random guest-session identifier, policy version accepted, start/expiry time, assigned address, and a pseudonymous device handle when the access controller requires one. Voucher or sponsor references should be stored only when that access mode is used.

## Proposed exclusions by default

Normal network access should **not** require:

- TLS interception or installation of a WW.CX interception certificate;
- payload/content inspection of encrypted traffic;
- storage of passwords, WireGuard private keys, or long-lived enrollment secrets in registration records;
- collection of browsing history as a standard access-control record;
- recording message, document, call, or application content merely because it traverses the network;
- mandatory identity collection from ordinary guests when anonymous click-through access is sufficient.

Security tooling that temporarily captures additional diagnostic data for a specific incident must be separately authorized, tightly scoped, and documented.

## DNS and security telemetry

DNS, threat-intelligence, abuse, and firewall telemetry may be used when required for network operation or incident response. The preferred configuration is aggregate or event-based logging rather than indiscriminate long-term per-user browsing records.

Any future detailed DNS or proxy logging should be separately enabled, visibly disclosed, access-controlled, and assigned an explicit retention period.

## Proposed retention

A reasonable initial target for ordinary authentication/session and network-access metadata is **30 days**, unless a shorter operational period is sufficient. Security events that are part of a documented incident may be retained longer when required for investigation, audit, legal hold, or remediation.

Retention periods should be approved before policy activation and implemented with automated expiry where practical.

## Access to records

Access to account/device and guest-session records should be limited to operators who need the information for administration, support, security, audit, or incident response. Administrative reads and changes should themselves be auditable where practical.

## Policy acceptance records

Acceptance records should contain the minimum facts necessary to prove what was accepted and when: policy version, accepting subject or guest session, timestamp, source, and expiration when applicable. Raw session secrets and enrollment tokens should not be retained as evidence.

## Transparency

The user-facing notice should summarize what data is collected, why it is used, how long it is normally retained, and how to contact WW.CX about access or privacy questions before acceptance is requested.