# Proposed Device Registration & Credential Lifecycle Policy

Status: **DRAFT / NOT ACTIVE**  
Audience: WW.CX private-network and VPN users

## Ownership

Each private/VPN device should belong to exactly one stable WW.CX account subject. Display names and usernames are conveniences and must not be treated as the ownership key.

A device changing owners should be revoked and re-enrolled for the new owner rather than transferring an existing private credential.

## Enrollment

A new device should be enrolled through an authenticated WW.CX account or an administrator-authorized invitation. Enrollment should create a device-specific credential and a device registration record.

The proposed default is one credential per device. A credential must not be reused across multiple devices merely for convenience.

## Private-key handling

The long-term target is that a client WireGuard private key is delivered only to the device being enrolled and is not retained as ordinary registration data.

Any implementation that temporarily stores a generated client configuration for provisioning must treat it as secret material, minimize the storage window, restrict filesystem access, and have a documented cleanup process. This requirement must be technically verified before the policy is activated.

## Friendly names

Users may assign and change a friendly device name. Renaming a device must not change its stable owner or silently replace its network credential.

## Re-registration and replacement

Users should be able to replace a VPN profile from My Account. Replacement should create a new one-time enrollment and should make clear whether the previous credential remains valid until the replacement is completed or is revoked immediately.

The safer default for a known-compromised or lost device is immediate revocation followed by fresh enrollment.

## Revocation

A user should be able to revoke access for a device they own. Administrators may revoke or quarantine a device for security, abuse, operational, or policy reasons.

Revocation should:

- invalidate the device's private-network/VPN access;
- preserve an audit record of the action and reason where applicable;
- avoid deleting historical policy-acceptance or security evidence required for audit;
- not affect unrelated devices owned by the same account.

## Lost, stolen, or compromised devices

Users should revoke the device as soon as reasonably possible. If the user cannot access My Account, an authorized administrator should be able to revoke or quarantine the device after identifying the account and device.

## Policy status

A registered device may still be in `pending`, `policy_update_required`, `quarantined`, or another restricted state. Device ownership alone does not guarantee active network access.

## Reauthentication

Credential replacement, revocation, ownership-sensitive changes, and policy acceptance should require a current authenticated WW.CX session. High-impact actions should require recent reauthentication when practical.

## Service and infrastructure devices

Non-user service devices should use an explicitly documented service identity or exemption rather than being silently attributed to an individual user. Service exemptions should be scoped, justified, auditable, and expire when practical.