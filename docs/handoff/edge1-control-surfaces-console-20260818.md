# Edge1 Control Surfaces Console Handoff — 2026-08-18

## Objective

Provide a private, authenticated Edge1 page that inventories and eventually brokers operator access to FreePBX, Asterisk and related internal interfaces without preserving unintended public control surfaces, while keeping legitimate public infrastructure and SIP/media peering functions distinct.

## Implemented repository state

Branch: `feature/control-surfaces-console-20260818`

Draft PR: `#354`

Implemented:

- `config/security/edge1-control-surfaces.json` — classified registry of public infrastructure, peering surfaces, private controls and internal services;
- `src/web/edge1-ops/control-surfaces/index.html` — read-only authenticated console UI;
- existing Edge1 security authentication adapter extended with exact routes for the console and registry;
- loopback adapter loads both assets from the repository;
- Apache staging example proxies only the explicit `/edge1-ops/control-surfaces/` prefix to the loopback authentication adapter;
- `tests/test_edge1_control_surfaces.py` enforces classification and no-private-control-as-peering invariants.

## Boundary decisions

Public infrastructure is kept separate from management:

- TCP 80/443 — Apache public ingress;
- UDP 51820 — WireGuard transport;
- UDP 123 IPv4 — accepted public NTP service.

Peering is a separately activatable service plane:

- current Kamailio TCP/UDP 5060 staging binding is recorded as firewall-blocked pending activation;
- target SIP/TLS peering is TCP 5061 through Kamailio, not direct Asterisk management exposure;
- UDP 10000-20000 is recorded as a conditional media range, not something to publish wholesale before RTPengine/SRTP policy is accepted.

Private controls are not peering dependencies:

- FreePBX Administration and UCP remain private-route candidates behind shared Apache ingress;
- Asterisk AMI 5038 remains loopback-only and must never be exposed raw to a browser;
- Asterisk HTTP 8088 remains loopback-only;
- Asterisk HTTPS/WSS 8089 remains classified private and is not required for SIP peering;
- Asterisk loopback PJSIP 5061 is the backend side of the intended Kamailio architecture;
- SSH, MariaDB, Node 8001/8003 and other internal services are not peering dependencies.

## Probe evidence limitation

An outside-in TCP probe was attempted from the ChatGPT execution container against the known Edge1 IPv4. The execution environment blocked arbitrary outbound TCP connectivity, so those failures are not Edge1 reachability evidence and are explicitly recorded as non-authoritative.

The repository therefore relies on accepted Edge1 listener/firewall evidence until a fresh authenticated host inventory and a genuine external scanner are available.

## Safety state

No live Edge1 change was performed.

No firewall, DNS, certificate, listener, route, Asterisk/FreePBX configuration, call traffic or peering activation was changed.

The committed authentication HTTP configuration remains `staged_disabled`; native FreePBX/Asterisk proxy controls remain disabled in the registry and UI.

## Validation

Repository diff reviewed through GitHub. Added policy-focused unit tests. GitHub Actions had not started a workflow for the draft PR at the time of this handoff, so CI is not claimed as passed.

## Required activation sequence

1. Obtain a fresh authenticated Edge1 listener/firewall inventory.
2. Run a genuine outside-in probe from a network that permits scanning the owned Edge1 host.
3. Reconcile the registry with current live evidence.
4. Run repository tests and existing security-auth regression suite.
5. Review and merge PR #354.
6. On Edge1, back up the authentication adapter and active Apache TLS vhost.
7. Deploy code/config with authentication routes still disabled and validate loopback health.
8. Review the exact Apache proxy insertion and authentication route activation as a privileged production change.
9. Activate only the authenticated Control Surfaces routes; do not activate native control proxies yet.
10. Validate unauthenticated denial, authenticated rendering, registry access, logout, audit, rate limits and rollback.
11. Design native FreePBX proxy access and allowlisted Asterisk diagnostic actions as a separate reviewed phase.
12. Keep SIP/media peering activation under its existing independent acceptance gates.
