# Project Big Bird / Edge1 evidence reconciliation — 2026-08-20

Status: CURRENT read-only reconciliation  
Scope: listener provenance, security-boundary residuals, Control Surfaces/Asterisk evidence, and DTMF external gate.

This record closes documentation ambiguity only. It does not change a listener, firewall, DNS, SIP, service, authentication policy, certificate, route, production traffic, carrier behavior, or retained evidence.

## 1. Fresh bounded Edge1 state

Direct bounded Edge1 diagnostics on 2026-08-20 report:

```text
BigBird AI              0.3.5-alpha.1 / healthy / enabled / read-only
Library integrity       ok
Operations API          healthy / 27 actions / mutations_enabled=false
shared engineering      234d00194cf7ef4abb6bdd466c7d9a6f1996fd99
immutable runtime       d326d4546abefa695a293266342a5c1075f010e2
listener raw classifier internal-service=37 / private-control=4 / unknown-needs-attribution=22
```

The two BigBird connector lifecycle units remain failed. Their source repair is merged in PR #478, but live repair acceptance is separate and remains incomplete.

## 2. Listener attribution reconciliation

The raw listener classifier is intentionally conservative. It still reports 22 rows as `unknown-needs-attribution`; current repository/live evidence is sufficient to attribute 18 of those rows without changing the classifier or network exposure.

### Attributed from current and accepted evidence

| Listener rows | Attribution | Evidence class | Disposition |
|---|---|---|---|
| UDP/TCP `10.77.0.1:53` | private DNS service on the WireGuard `wg0` interface | LIVE interface/address + accepted Edge1 network architecture | Expected private infrastructure; no change |
| UDP `0.0.0.0:123` and `[::]:123` | Chrony public NTP/time-authority service | accepted public NTP/time-authority activation records + current service/network state | Expected public infrastructure; no change |
| UDP `0.0.0.0:51820` and `[::]:51820` | WireGuard transport | LIVE `wg0` interface + accepted VPN architecture | Expected VPN infrastructure; no change |
| UDP `0.0.0.0:41641` and `[::]:41641` | Tailscale transport | LIVE `tailscale0` interface/routes + accepted platform architecture | Expected private overlay infrastructure; no change |
| UDP/TCP `10.77.0.1:5060` and `89.147.109.253:5060` | Kamailio SIP signaling | current bounded Kamailio process/SIP-listener evidence + accepted telephony architecture | Expected SIP infrastructure; no change |
| TCP `0.0.0.0:4460` and `[::]:4460` | NTS-KE / Time Authority | accepted NTS live-activation records and maintained Chrony NTS configuration | Expected time-security infrastructure; no change |
| TCP `*:8001` and `*:8003` | FreePBX UCP Node/PM2 under `freepbx.service` | accepted 2026-08-01 wildcard-service attribution audit | Known application listeners; public ingress policy and WireGuard consumer boundary already documented; no change |
| TCP `*:80` and `*:443` | Apache public HTTP/HTTPS front door | current Apache/front-door accepted state | Expected web front door; no change |

### Still unresolved after bounded evidence pass

Only four raw-classifier rows remain without sufficiently specific owner/purpose evidence in the currently mounted bounded tools:

```text
UDP  0.0.0.0:57784
UDP  [::]:51550
TCP  100.115.195.54:40463
TCP  fd7a:115c:a1e0::5d39:c337:42639
```

The two TCP addresses are on the live Tailscale interface, but address locality alone is not sufficient to claim exact process/consumer ownership. The dynamic UDP ports likewise remain unclassified. Preserve them as provenance items. Do not stop, firewall, narrow, restart, or rebind them merely to reduce the count.

**Result:** 18 of the 22 conservative raw `unknown-needs-attribution` rows are now evidence-attributed; 4 remain genuinely unresolved. The runtime classifier count remains 22 until its static classification logic is deliberately changed; this documentation reconciliation does not alter that logic merely to improve a metric.

## 3. Security-boundary residual evidence

The exact protected evidence directory is now identified and retained by durable transcript evidence:

```text
/var/lib/wwcx-deployment-evidence/edge1-security-boundary-live-inventory/20260819T060856Z
```

Accepted aggregate:

```text
security_inventory_rc=0
records=164
mapped=160
missing_known=0
unknown_preserved=4
filesystem_anomaly=1
apache_config_test_passed=true
credentials_collected=false
live_configuration_changed=false
source_tree_mutated=false
traffic_controls_changed=false
```

Retained evidence hashes:

```text
result.json
f38f6e6d2fc099b1212fa26f00831f8e4abd0cdf76e366ab48f07227bc2dce18

sha256-manifest.txt
e7941f46073ef7c8da477ca949cb91f2377fb77c41b9cf8948da9fc02ded5f3a
```

The protected directory is known; however the currently mounted read-only Operator does not expose bounded reads of `reconciliation.json` or `public-filesystem-anomalies.json`. The four preserved unknowns and one filesystem anomaly therefore remain **BLOCKED ON BOUNDED METADATA/PATH/HASH ACCESS**. Their contents must not be opened merely to force classification, and the preserved unknowns must not be deleted.

## 4. Control Surfaces / Asterisk evidence housekeeping

A durable 2026-08-19 transcript retains the corrected Asterisk warning-follow-up audit:

```text
asterisk_warning_audit_rc=0
asterisk_warning_evidence=/var/lib/wwcx-deployment-evidence/asterisk-warning-followup/20260819T060845Z
mode=read-only
```

The retained extract confirms loopback PJSIP transport/listener `127.0.0.1:5061`; subsequent current bounded Asterisk diagnostics use the accepted Asterisk-owned fixed snapshot path and report native status successfully. Do not widen the Asterisk control socket.

The same 2026-08-19 capture records:

```text
control_surfaces_inventory_rc=126
```

Therefore that historical full executable inventory run must **not** be represented as successful. The repository script packaging/executable-mode issue was subsequently corrected, and current bounded Operator diagnostics provide fresh listener/component state, but no later durable `scripts/control-surfaces-live-inventory.sh` execution manifest with `rc=0` was found in the available archive. The full-script retained manifest remains a bounded execution/evidence task when an authenticated execution path is available.

## 5. DTMF provider response gate

Gmail was rechecked on 2026-08-20. The newest VoIP.ms response found after the technical follow-up remains the 2026-08-14 message stating there were no updates. No substantive technical response was found.

```text
response_state=pending
provider_reply_received=false
matrix_update_allowed=false
live_test_authorized=false
```

No carrier matrix update, production call, or DTMF transmission is authorized by this state.

## 6. Closeout classification

| Work item | Current status |
|---|---|
| Exact security-boundary evidence directory | COMPLETE / DURABLY IDENTIFIED |
| Four preserved security unknowns + one filesystem anomaly | BLOCKED on bounded metadata/path/hash access |
| Corrected Asterisk warning-follow-up audit retention | COMPLETE / DURABLY IDENTIFIED |
| Full executable Control Surfaces manifest | OPEN — historical run was `rc=126`; no later retained `rc=0` manifest found |
| Listener provenance | 18/22 raw unknown rows evidence-attributed; 4 genuinely unresolved |
| DTMF provider reply | EXTERNALLY BLOCKED / PENDING |

This record is an evidence reconciliation, not an exposure-reduction authorization.
