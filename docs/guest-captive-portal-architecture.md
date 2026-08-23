# Proposed Guest Captive Portal Architecture

Status: **architecture proposal only**  
Production activation authorized: **no**

## Decision

Guest access should be implemented as a **separate trust domain** from the WW.CX private network and Edge1 WireGuard device-registration system.

A guest should be able to get internet access through a captive portal without receiving a WW.CX account, private-network device ownership, a WireGuard profile, or access to internal resources.

## Target topology

```text
Guest device
   |
Guest SSID / guest wired port
   |
Dedicated guest VLAN / subnet
   |
Guest gateway + captive access controller
   |          \
   |           -> Captive portal / policy service
   |
Internet egress/NAT

DENY -> WW.CX private VLANs
DENY -> Edge1 management surfaces
DENY -> WireGuard/private address space
DENY -> server/storage/telephony/operations networks
```

The guest segment should not be bridged to private LANs. IPv4 and IPv6 isolation must be equivalent.

## Components

### 1. Guest access segment

A dedicated SSID and VLAN/subnet should contain guest devices. Client isolation should be enabled where the access-point/controller supports it.

No existing private subnet or WireGuard address pool should be reused for guests.

### 2. Guest gateway

The guest gateway should be the only routed path out of the guest segment. Before portal acceptance it should permit only the minimum walled-garden traffic needed for:

- DHCP and required local network control traffic;
- DNS through the approved guest resolver path;
- the WW.CX captive portal and its static assets;
- operating-system captive-network detection endpoints where required for reliable portal launch;
- certificate revocation/validation traffic only where technically necessary.

Arbitrary private-network destinations remain denied both before and after acceptance.

### 3. Captive portal

The portal should display:

- WW.CX guest branding;
- the current guest policy version;
- a concise privacy summary;
- session duration and material limitations;
- an explicit **Accept & Connect** action.

The portal should use HTTPS at its real hostname. The network should not attempt TLS interception. Modern HTTPS requests that cannot be safely redirected should fail normally until the operating system opens the captive portal through its supported captive-detection flow.

### 4. Guest session service

Guest sessions should be stored separately from private/VPN devices. A proposed guest-session record contains only:

- random session ID;
- active guest policy version and acceptance timestamp;
- session start, last activity, and expiry;
- assigned guest address;
- pseudonymous device handle when the controller requires device continuity;
- optional voucher/sponsor reference;
- optional aggregate byte counters and reason for termination.

Where practical, a controller MAC address should be converted to a keyed/pseudonymous handle before it leaves the network-control layer. Raw device identifiers should not become general application identifiers.

### 5. Internet egress

After portal acceptance, the gateway authorizes that guest session for internet egress only. Suggested controls for review include:

- per-client bandwidth fairness;
- connection-rate/abuse limits;
- outbound abuse controls for high-risk services when operationally justified;
- DNS security appropriate to an untrusted guest network;
- no inbound connections from the internet to guest clients;
- no guest-to-private forwarding;
- no guest-to-guest forwarding where client isolation is available.

## Identity modes

The portal can support more than one guest flow without changing the trust boundary:

### Anonymous click-through — recommended default

No WW.CX account is required. The user accepts the guest policy and receives a short-lived guest session.

### Voucher access

A host/operator issues a one-time or time-limited voucher. The voucher controls duration or entitlement but does not create private-network identity.

### Sponsored guest

A WW.CX account holder may sponsor a guest session. The sponsor reference is recorded for audit, but the guest still remains on the guest network.

### Contractor/temporary user

A temporary worker may use a WW.CX identity for portal authentication if desired, but successful authentication still grants **guest-segment internet access only** unless the person separately goes through the private-device/VPN enrollment process.

## Policy namespaces

Private/VPN policies and guest policies should be versioned separately:

```text
network-YYYY-NN   private/VPN registration policy bundle
guest-YYYY-NN     guest captive-portal policy bundle
```

Acceptance of one namespace never satisfies the other.

The existing registration policy store can provide design patterns for versioning and audit, but guest sessions should have their own tables/service so anonymous visitors are not forced into the account-owned device model.

## Portal discovery

The implementation should support platform-standard captive-network discovery rather than relying on aggressive DNS or HTTPS hijacking. Exact behavior should be validated against current iOS/iPadOS, Android, Windows, macOS, and ChromeOS clients during the lab phase.

## Security requirements

Before production activation, validation should prove:

- guest-to-private traffic is denied for IPv4 and IPv6;
- guest-to-WireGuard/private address ranges is denied;
- private DNS/admin/operations endpoints cannot be reached from the guest segment;
- unauthenticated guests can reach only the walled garden;
- accepted guests can reach the internet but not internal networks;
- session expiry immediately removes guest authorization;
- policy-version changes affect new/re-authenticated sessions as designed;
- spoofing another guest's IP or identifier does not inherit that guest's session;
- portal failure fails closed for private-network access;
- no TLS interception is present;
- audit and retention match the approved privacy notice.

## Suggested implementation phases

### Phase 0 — policy and design

Review these proposed documents. No network changes.

### Phase 1 — isolated lab

Create the portal/session software against a test network namespace or isolated lab VLAN with no route to production private networks.

### Phase 2 — guest segment pilot

Create the dedicated guest SSID/VLAN, DHCP/DNS path, gateway, and walled garden. This phase requires explicit approval because it changes production routing/firewall/DNS/access infrastructure.

### Phase 3 — limited guest pilot

Allow a small number of invited guests. Verify device compatibility, policy UX, expiry, abuse controls, privacy output, and rollback.

### Phase 4 — normal service

Enable broader guest access only after successful pilot evidence and an approved guest policy version.

## Operational separation from VPN device management

The My Account **Devices & network** page remains for account-owned private/VPN devices. A future guest portal should have a separate guest-session/operator view, for example:

- user-facing: `guest.ww.cx` or another approved portal hostname;
- operator-facing: Network -> Guest Access;
- private/VPN fleet: Network -> VPN & Devices.

The exact hostname, VLAN IDs, subnets, firewall rules, DNS behavior, and access-point configuration are deliberately not assigned in this proposal. Those are production network decisions that should be chosen during implementation after current infrastructure is inspected.