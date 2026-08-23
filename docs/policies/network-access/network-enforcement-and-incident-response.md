# Proposed Network Enforcement, Quarantine & Incident Response Policy

Status: **DRAFT / NOT ACTIVE**  
Network enforcement currently authorized by this document: **no**

## Purpose

Define how WW.CX should respond when a device or session is unregistered, out of policy, compromised, abusive, or otherwise unsafe without making enforcement arbitrary or invisible.

## Proposed states

Private/VPN devices should use explicit, auditable states such as:

- `pending` — known device, but required policy/registration conditions are not complete;
- `registered` — current requirements are satisfied;
- `policy_update_required` — a newer policy version requires renewed acceptance;
- `quarantined` — network access is restricted because of a security, abuse, or administrative condition;
- `exempt` — a documented exception temporarily satisfies a specific requirement.

Status labels should describe the control decision; they should not be used as unsupported claims about whether a device is malware-free or generally trustworthy.

## Proposed quarantine triggers

A device may be quarantined when there is a reasonable operational basis, including:

- the owner reports it lost, stolen, or compromised;
- its network credential is revoked;
- credible evidence indicates malware, credential theft, abuse, or unauthorized access;
- the device is intentionally bypassing network controls;
- the device creates a material risk to WW.CX systems or other users;
- an administrator must contain an active incident while facts are established.

Policy expiry by itself should normally produce `pending` or `policy_update_required`, not a security quarantine, unless another security condition exists.

## Proposed quarantine behavior

When an enforcement adapter is eventually activated, quarantine should be narrowly designed. Preferred outcomes are:

- deny private-network access;
- allow only the minimum remediation, policy, support, or update destinations required for recovery where practical;
- preserve access to emergency/public internet services only where the underlying network design supports doing so safely;
- avoid redirecting or decrypting arbitrary HTTPS traffic.

Exact firewall/DNS behavior requires separate engineering approval and testing.

## Exemptions

An exemption should identify:

- the exact device or service;
- the specific requirement being exempted;
- the reason;
- the approving actor;
- start and expiration time when practical.

An exemption must not silently disable unrelated security controls. Permanent exemptions should be exceptional and periodically reviewed.

## Administrative actions

Administrators should be able to view status, quarantine, release, and manage exemptions through a protected operator surface. User self-service should remain limited to the user's own devices and should not expose fleet-management capabilities.

## Audit and notification

Material access decisions should produce an audit event with the device/session identifier, actor or source, action, time, and reason category. Sensitive diagnostic details should remain in restricted logs rather than user-facing messages.

Where practical, the account holder should be told that a device is restricted and given a non-sensitive explanation and recovery path.

## Incident preservation

During a documented incident, relevant logs may be retained beyond ordinary retention long enough to investigate and remediate the issue. Preservation should be scoped to the incident and documented rather than becoming an indefinite default.

## Activation boundary

Merging or approving this policy text does not enable enforcement. Production firewall, routing, DNS, proxy, captive-portal, authentication, or VPN changes require their own implementation review, explicit authorization, rollback plan, and post-change validation.