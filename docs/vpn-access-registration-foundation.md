# VPN Access Registration Foundation

Status: deployed on Edge1 as a registration-only pilot; enforcement intentionally absent

## Purpose

Provide a durable policy and consent record for devices that use Edge1 as a
WireGuard egress gateway. This phase stores registration state only. It does
not inspect, redirect, permit, deny, cache, decrypt, or otherwise change
network traffic.

## Safety boundary

This phase does **not**:

- change WireGuard peers or configuration;
- create or update nftables or iptables rules;
- change Unbound, DNS responses, or Spamhaus enforcement;
- install, configure, or enable Squid;
- redirect HTTP or HTTPS;
- perform TLS interception;
- enable registration writes by default.

`EDGE1_VPN_REGISTRATION_WRITES_ENABLED` defaults to `false`. The Operations
Center export always reports `enforcement_active: false`.

## Stored state

The existing Operations API SQLite database gains isolated tables for:

- versioned privacy and acceptable-use policies;
- devices identified by a SHA-256 fingerprint of the WireGuard public key;
- assigned VPN addresses, display name, owner, and observation timestamps;
- immutable policy-acceptance records with a default 30-day expiry;
- registration, cache, proxy, DNS-filtering, and detailed-logging exemptions;
- per-device DNS, proxy, cache, logging, and Spamhaus policy flags;
- quarantine and release state;
- registration-specific audit events.

Raw WireGuard public keys are never stored. Exemptions require a reason and
approving actor and may have an expiry. Quarantine takes precedence over
acceptance or exemption when status is calculated.

Activating a new policy version immediately places devices that accepted an
older version into `policy_update_required`, even when their 30-day acceptance
period has not elapsed.

## Authenticated API

All endpoints reuse the Operations API HMAC signature, clock-skew, nonce, and
loopback-only controls.

Read endpoints:

```text
GET /v1/vpn-access/summary
GET /v1/vpn-access/devices
GET /v1/vpn-access/policies
GET /v1/vpn-access/audit
```

Write endpoints, separately gated by
`EDGE1_VPN_REGISTRATION_WRITES_ENABLED=true`:

```text
POST /v1/vpn-access/policies
POST /v1/vpn-access/devices
POST /v1/vpn-access/acceptances
POST /v1/vpn-access/exemptions
POST /v1/vpn-access/exemptions/revoke
POST /v1/vpn-access/quarantine
POST /v1/vpn-access/policy-flags
```

No endpoint accepts a command, SQL statement, filesystem path, service name,
firewall rule, or arbitrary enforcement target.

## Operations Center

`vpn_access_registration_exporter.py` writes a privacy-limited JSON summary
containing counts, policy version, next expiry, and recent event types. It
does not export device names, owners, addresses, public-key fingerprints,
acceptance actors, reasons, or detailed audit payloads.

The optional systemd timer refreshes this summary every 60 seconds. Installing
or enabling the timer is a separate operator action.

## Validation

```sh
python3 tests/validate_vpn_access_registration.py
python3 -m unittest tests.test_edge1_operations_api -v
python3 -m compileall -q server tests
```

The validation covers key hashing, new-device state, policy history, 30-day
expiry, exemption expiry and revocation, policy flags, quarantine, audit
events, invalid input, and privacy-limited atomic export.

## Production activation sequence

1. Review and merge the repository change.
2. Back up `/var/lib/edge1-operations-api/audit.sqlite3`.
3. Deploy the code with registration writes still disabled.
4. Start the API and confirm `/healthz` reports enforcement inactive.
5. Create and legally review the first policy version.
6. Enable registration writes for a limited administrative pilot.
7. Enable the summary exporter only after verifying output permissions.
8. Review collected state before designing any enforcement adapter.

Network enforcement requires a separate change, test plan, approval, and
rollback procedure.

## Edge1 pilot activation (2026-08-23)

The registration-only pilot is active on Edge1 with:

- `EDGE1_VPN_REGISTRATION_WRITES_ENABLED=true` while global operations mutations remain disabled;
- `vpn_enforcement_active=false`;
- the privacy-limited registration exporter enabled on a 60-second timer;
- invite/enrollment devices synchronized into the registration API through authenticated HMAC requests;
- revoked enrollment devices quarantined in registration state when they already have a registration record;
- no active policy version yet, so enrolled devices remain `pending` until approved policy text is activated and accepted.

The public invite route and protected admin route were exercised end-to-end. A reversible smoke enrollment added one WireGuard peer and revocation restored the original peer configuration.

## Account ownership integration (2026-08-23)

WW.CX Account Settings now treats VPN devices as account-owned assets. The stable owner is the Business159 assertion subject (`wwcx-user-<id>`), not a username or display name. The enrollment-to-registration sync carries that subject into the registration store.

Self-service is restricted to narrow scopes: `edge1.vpn.self.read`, `edge1.vpn.self.enroll`, `edge1.vpn.self.rename`, `edge1.vpn.self.revoke`, and `edge1.vpn.self.policy.accept`. Each account request uses a short-lived, one-time signed assertion and is checked against the device owner before any state change.

No policy was activated or accepted as part of this integration. Registration enforcement remains disabled.
