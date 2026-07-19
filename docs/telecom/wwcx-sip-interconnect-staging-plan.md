# WW.CX SIP Interconnect and Numbering Node Staging Plan

Status: production-ready staging design; no live deployment authorized by this document.

## Confirmed baseline

- Edge1 public IPv4: `89.147.109.253`.
- No globally routable IPv6 address or IPv6 default route is present.
- Apache is listening on TCP 443.
- Asterisk is listening on UDP 5060.
- Nothing has yet been verified listening on TCP 5061.
- DNS advertises `_sips._tcp.ww.cx` to `interconnect.ww.cx:5061`.

## Safety boundary

This repository may contain sanitized source, templates, validation scripts, runbooks, and rollback instructions. It must not contain credentials, private keys, production databases, unredacted diagnostics, peer secrets, or private customer records.

The staging work must stop before any change that:

- changes a live FreePBX transport, trunk, route, or dialplan;
- opens or closes a firewall port;
- binds a new public listener;
- issues, replaces, or exposes a production certificate or private key;
- publishes or removes DNS records;
- deploys or merges into production without a reviewed rollback path.

## Target architecture

```text
Public SIP peer
    |
    | SIP over TLS, TCP 5061
    v
Kamailio interconnect edge
    |
    | loopback-only SIP backend
    v
Asterisk / FreePBX
    |
    +-- approved inbound context
    +-- existing trunks and extensions remain unchanged

Kamailio / policy service
    |
    | localhost HTTP
    v
WW.CX numbering node, 127.0.0.1:8093
```

## Implementation phases

1. Capture a read-only baseline and backups.
2. Validate host packages, listeners, certificates, firewall layers, and FreePBX dependencies.
3. Complete the localhost-only numbering node and its import/lookup tests.
4. Install Kamailio packages without enabling a public listener.
5. Configure a loopback TLS listener using a non-production test certificate.
6. Validate deny-by-default routing, malformed traffic handling, rate limits, and open-relay rejection.
7. Prepare a separate loopback Asterisk backend transport and restricted inbound context, but do not apply them automatically.
8. Prepare certificate deployment and renewal hooks without issuing or replacing a certificate.
9. Prepare firewall changes as an operator-reviewed patch, not an automatic action.
10. Perform external TLS and SIP OPTIONS tests only after an approved public activation.
11. Onboard one allowlisted peer before any broader interconnection.
12. Add RTPengine and SRTP policy before general production traffic.

## Production acceptance gates

- Existing FreePBX calls and trunks remain functional.
- Kamailio configuration validation passes.
- Certificate chain and hostname validation pass.
- Unknown peers, public REGISTER, and open relay attempts are rejected.
- The Asterisk backend is loopback-only.
- The inbound context cannot originate arbitrary PSTN calls.
- Rate limits, logs, alerts, certificate renewal, and rollback are tested.
- External SIP OPTIONS succeeds over TLS.
- No AAAA record is published until routed IPv6 exists.

## Known unresolved items

- Current FreePBX firewall and upstream provider-firewall policy have not been captured.
- Existing Asterisk UDP 5060 dependencies have not been fully inventoried.
- Certificate coverage for `interconnect.ww.cx` has not been verified.
- RTP and SRTP policy has not been selected.
- Peer identity, authorization, call-rate, codec, caller-ID, and emergency-calling policies need operator approval.
- The earlier numbering-node installer is incomplete and must not be deployed in its current form.

## Rollback principle

Every applied phase must be independently reversible. Public activation must be reversible by disabling the Kamailio listener and withdrawing the firewall allowance while leaving existing Asterisk service untouched. DNS withdrawal is a separate operator action.