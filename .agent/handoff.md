# Edge1 Operations Handoff

Date: 2026-08-01  
Repository: `johnkaminski727-alt/edge1-management-interface`  
Authoritative branch: `main`  
Accepted security live revision: `a06f035e7fcf933a03ec752c66ce0261c5a65ba7`  
Minimum confirmed alerting live repository state: contains `03d219e853bd8a373cd9d0503c45579901615017`

## Accepted live baseline

Security Correlation and Network Defense remain live and accepted. Network-source freshness is `600` seconds, overall state is `limited`, verified enforcement count remained `1`, DNS is `not_staged`, DNS enforcement is false, and traffic controls and timer state were unchanged.

Asterisk and the offline alerting laboratory now have a separately accepted live baseline:

- Asterisk updated from `22.8.2` to `22.10.1`;
- guarded package simulation and apply completed with zero active calls;
- Asterisk restarted and the running binary matched the installed package;
- Kamailio remained active;
- base media, DTMF, DSP and PJSIP modules remained loaded;
- no PJSIP endpoints and no alerting dialplan matches were observed;
- the offline CAP-CP/EBS laboratory was installed under `/opt/wwcx-alerting-lab`;
- bilingual synthetic CAP-CP structural and lifecycle tests passed;
- no CAP feed, `Actual` alert path, call/page route, tone transmission, carrier route or public distribution was enabled.

Protected evidence:

```text
/var/lib/wwcx-deployment-evidence/edge1-project-completion-preflight/20260730T193415Z
/var/lib/wwcx-deployment-evidence/network-defense-freshness/20260730T195031Z
/var/lib/wwcx-deployment-evidence/asterisk-security-update/20260731T231305Z
/var/lib/wwcx-deployment-evidence/asterisk-security-update/20260731T233728Z
/var/lib/wwcx-deployment-evidence/alerting-lab-install/20260731T233821Z
```

Operator-local alerting evidence:

```text
/home/wwadmin/edge1-alerting-rollout-20260731T233717Z
```

## Completed repository work

- protected Suricata retention runtime and closeout: PRs #138-139;
- minimized public-summary route, CSP, staging runtime, and closeout: PRs #140-145;
- authenticated detailed-operations boundary and closeout: PRs #146-147;
- restricted-artifact migration manifest and closeout: PRs #148-149;
- security-boundary live inventory bundle: PR #151, merged as `85d9a9cb43e5ca4dd09f2d955b00997ef28e2cf0`;
- test-only EBS and CAP-CP compatibility foundation: PR #157, merged as `7456304d41063075be15ff894af815877dd8a554`;
- alerting continuity state: PR #159, merged as `03d219e853bd8a373cd9d0503c45579901615017`.

## Alerting acceptance record

```text
docs/telecom/wwcx-alerting-live-acceptance-20260731.md
```

The record distinguishes installed offline compatibility tooling from operational public-alert capability. Compatibility is not certification.

## Residual alerting warnings

1. `pjsip show transports` returned `No objects found`, although Asterisk owned UDP `127.0.0.1:5061`.
2. The generated legacy SysV-backed service wrapper was active, while systemd enablement reported disabled.
3. Asterisk TCP `8089` was bound to a non-loopback wildcard address.

These warnings do not establish a current outage, but they must be reconciled before transport, boot-policy, listener, certificate or firewall changes.

## Exact alerting continuation

Through the authenticated Edge1 shell:

```sh
cd /opt/edge1-management-interface
git pull --ff-only origin main
git status --short --branch
sudo sh tools/alerting/asterisk_warning_followup_audit.sh \
  --expected-host edge1.ww.cx
```

Capture the output into a new protected evidence directory before deciding whether any configuration change is required. The follow-up audit is read-only.

## Alerting remaining sequence

1. reconcile PJSIP runtime-object visibility with the listener and sanitized configuration;
2. verify SysV startup links and reboot persistence before any service-enable change;
3. verify TCP `8089` TLS identity, authentication, firewall reachability and operational need;
4. retain the laboratory in offline/test-only mode;
5. obtain written source authority, trust anchors and redistribution terms before connecting CAP-CP ingress;
6. implement persistent trust, replay, update/cancel, expiry, event/location references, geographic targeting, bilingual rendering, accessibility, audit and retention;
7. require separate production authorization and conformance evidence before `Actual` alerts, call/page delivery, tone generation, carrier routing or public claims.

## Security inventory continuation

```sh
cd /opt/edge1-management-interface
git pull --ff-only origin main
git status --short --branch
sudo sh tools/security/edge1-security-boundary-live-inventory.sh
```

Review `result.json`, `reconciliation.json`, `public-filesystem-anomalies.json`, `apache-boundary-readiness.json`, `route-matrix.tsv`, and `sha256-manifest.txt` before any security-boundary staging.

## Safety boundary

No operational CAP feed, `Actual` alert acceptance, alert origination, Asterisk page/call route, EBS/EAS tone transmission, carrier route, public alert distribution, regulatory certification claim, DNS, Unbound, RPZ, nftables, firewall, certificate, authentication, public route, production-traffic cutover, pruning, evidence deletion, or data deletion is authorized by this handoff.
