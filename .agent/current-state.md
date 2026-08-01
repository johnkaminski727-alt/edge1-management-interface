# Current State

Last verified: 2026-08-01  
Repository: `johnkaminski727-alt/edge1-management-interface`  
Authoritative branch: `main`  
Accepted security live revision: `a06f035e7fcf933a03ec752c66ce0261c5a65ba7`  
Minimum confirmed alerting live repository state: contains `03d219e853bd8a373cd9d0503c45579901615017`  
DTMF readiness implementation merge: `0703b88b227b346e022a40ca931e34d0874559cd`  
Repository state used for DTMF live acceptance: `a600a341bdaaefde8b6bde89cfb9dba48877f500`

## Verified live baseline

- Security Correlation and Network Defense are live and accepted.
- Suricata drill-down, caching, normalization, and enrichment are live.
- Network Defense applies the accepted network-source freshness threshold of `600` seconds.
- Overall Network Defense state is `limited`.
- DNS remains `not_staged`; DNS enforcement is false.
- Verified enforcement count remained `1` before and after freshness activation.
- Traffic controls and Network Defense timer state remained unchanged.
- Asterisk was successfully updated from directly observed version `22.8.2` to `22.10.1`.
- The guarded update completed with zero active calls, preserved configuration evidence, restarted the PBX, and validated the running binary against the installed package.
- Kamailio remained active after the PBX restart.
- `app_playtones`, `app_senddtmf`, DSP, `chan_pjsip`, `res_pjsip`, and `res_pjsip_sdp_rtp` were running after the update.
- No PJSIP endpoints and no alerting-related dialplan matches were observed.
- The authenticated DTMF readiness audit completed with exit code `0`, one warning, zero failures, and no runtime mutation.
- Runtime `SendDTMF()` help advertised `0-9`, `*`, `#`, and `A-D`.
- The offline DTMF probe passed all sixteen keypad symbols and recorded RFC 4733 event range `0-15`.
- No configured PJSIP endpoint DTMF-policy records were found, so carrier and end-to-end DTMF behavior remain unverified.
- The offline alerting laboratory is installed under `/opt/wwcx-alerting-lab`.
- The installed bilingual CAP-CP structural fixture and lifecycle/replay smoke test both passed with no errors or warnings.
- No CAP feed, `Actual` alert path, call origination, page route, alert-tone transmission, carrier route, DTMF transmission, or public alert distribution was enabled.

Protected live evidence:

```text
/var/lib/wwcx-deployment-evidence/edge1-project-completion-preflight/20260730T193415Z
/var/lib/wwcx-deployment-evidence/network-defense-freshness/20260730T195031Z
/var/lib/wwcx-deployment-evidence/asterisk-security-update/20260731T231305Z
/var/lib/wwcx-deployment-evidence/asterisk-security-update/20260731T233728Z
/var/lib/wwcx-deployment-evidence/alerting-lab-install/20260731T233821Z
/var/lib/wwcx-deployment-evidence/asterisk-dtmf-readiness/20260801T073955Z
```

Operator-local rollout evidence:

```text
/home/wwadmin/edge1-alerting-rollout-20260731T233717Z
```

## Completed repository programs

- Protected Suricata retention runtime and closeout: PRs #138-139.
- Minimized public-summary route, CSP, staging runtime, and closeout: PRs #140-145.
- Authenticated detailed-operations browser/session boundary and closeout: PRs #146-147.
- Restricted-artifact migration manifest and closeout: PRs #148-149.
- Security-boundary live inventory bundle merged through PR #151 as `85d9a9cb43e5ca4dd09f2d955b00997ef28e2cf0`.
- Test-only EBS and CAP-CP compatibility foundation merged through PR #157 as `7456304d41063075be15ff894af815877dd8a554`.
- Alerting continuity state merged through PR #159 as `03d219e853bd8a373cd9d0503c45579901615017`.
- Read-only Asterisk DTMF inventory, offline 16-key probe, capability matrix, and runbook merged through PR #197 as `0703b88b227b346e022a40ca931e34d0874559cd`.

No public-summary staging, authenticated restricted route, restricted release, detailed-artifact migration, public cutover, detailed-artifact removal, protected-retention installation, operational CAP feed, `Actual` alert handling, alert origination, Asterisk alert dialplan, page delivery, alert-tone transmission, DTMF transmission, carrier routing, or public alert distribution has occurred.

## Alerting compatibility live acceptance

Accepted live changes:

- Asterisk `22.10.1` installed and running;
- Asterisk restart completed successfully;
- zero active channels and calls after restart;
- offline laboratory installed under `/opt/wwcx-alerting-lab`;
- synthetic CAP-CP `Test`/`Restricted` bilingual validation passed;
- lifecycle/replay smoke validation passed;
- protected evidence recorded and retained.

Acceptance record:

```text
docs/telecom/wwcx-alerting-live-acceptance-20260731.md
```

## DTMF readiness live acceptance

Authenticated execution on `edge1.ww.cx` as `wwadmin` accepted the local read-only DTMF result.

Acceptance record:

```text
docs/telephony/asterisk-dtmf-readiness-live-acceptance-20260801.md
```

Evidence and hashes:

```text
/var/lib/wwcx-deployment-evidence/asterisk-dtmf-readiness/20260801T073955Z/operator-console.txt
SHA-256: e1676f4caa8ff56caf91049080f20b41a46f654e678b64eca3c17fd628c786f4

/var/lib/wwcx-deployment-evidence/asterisk-dtmf-readiness/20260801T073955Z/evidence-files.sha256
SHA-256: 8424ad369ccb0f9c2a2990f3320572a44c1543ce0963e4b58fd0c71cdadd3107
```

Accepted:

- Asterisk `22.10.1` local DTMF modules and CLI capability;
- all sixteen offline symbols `0-9`, `*`, `#`, and `A-D`;
- RFC 4733 event-range model `0-15`;
- zero calls, channels, processed calls, transmissions, and runtime mutations.

Still unverified:

- configured endpoint or trunk `dtmf_mode` policy;
- live SDP negotiation;
- carrier, SBC, gateway, SIP INFO, in-band, codec, transcoding, and end-to-end behavior;
- emergency-calling paths and every production route.

## Residual alerting warnings

1. `pjsip show transports` returned `No objects found`, although the Asterisk process owned UDP `127.0.0.1:5061`. Runtime object visibility and sanitized transport configuration need reconciliation.
2. The legacy SysV-backed Asterisk wrapper was active, while `systemctl is-enabled asterisk` reported disabled. Boot persistence is not yet accepted.
3. Asterisk TCP `8089` listened on a non-loopback wildcard address. TLS, certificate identity, authentication, firewall reachability, and operational need require read-only verification.

The repository includes a read-only follow-up audit:

```text
tools/alerting/asterisk_warning_followup_audit.sh
```

No listener, firewall, certificate, service-startup, transport, or dialplan change is authorized by the audit.

## Security-boundary live inventory repository completion

The authenticated read-only host-evidence bundle is implemented and merged.

Assets:

- `config/security/edge1-security-completion-authorization-20260730.json`;
- `tools/security/edge1-security-boundary-live-inventory.sh`;
- `tools/security/reconcile-edge1-live-inventory.py`;
- `tools/security/redact-edge1-boundary-text.py`;
- `tests/test_edge1_security_boundary_live_inventory.py`;
- runbook, validation checklist, register, and continuity records.

Exact implementation head `4a18c05f2a6f31369a3abfa695330ac5bf39d40a` passed `Validate repository` run 662 and `Edge1 Operator Validation` run 494, then merged through PR #151 as `85d9a9cb43e5ca4dd09f2d955b00997ef28e2cf0`.

The bundle records exact public-tree hashes and modes, filesystem anomalies, manifest reconciliation, Apache/module readiness, redacted service definitions, anonymous route/header observations, listeners, capacity, candidate roots, audit metadata, retention metadata, and an evidence SHA-256 manifest. It does not collect credentials, secret values, cookie values, environment dumps, SSH material, private keys, password-file contents, or audit-log contents.

## Telephony next gates

1. reconcile runtime PJSIP endpoint visibility and authoritative FreePBX/generated endpoint-policy sources without changing configuration;
2. populate the sanitized carrier DTMF capability matrix from provider documentation only;
3. keep carrier and end-to-end paths `unverified` pending separate controlled-test authority;
4. do not originate calls, transmit DTMF, alter routes, or test emergency-calling paths under the read-only acceptance.

## Alerting next gates

1. run and review `tools/alerting/asterisk_warning_followup_audit.sh` on Edge1;
2. reconcile the PJSIP CLI/socket discrepancy without changing transport configuration;
3. verify SysV boot links and generated service behavior before any startup-policy change;
4. verify local TLS identity, authentication and firewall reachability for TCP `8089` before any listener decision;
5. obtain written authority and trust details before connecting a CAP-CP source;
6. implement persistent issuer trust, signatures where required, reference lists, replay state, geographic policy, bilingual rendering, accessibility, audit and retention before any delivery adapter;
7. keep `Actual` alerts, call/page delivery, tone generation, carrier routing and public compatibility claims blocked pending separate authorization and conformance evidence.

## Security next gates

1. run the merged inventory on a clean authenticated Edge1 `main` checkout;
2. review unknown, missing, prefix-contained, duplicate, stale, historical, and operator-maintained artifacts;
3. verify an actually available approved identity-provider/Apache adapter path;
4. construct restricted and public staging installers from measured host evidence;
5. preserve authentication-first, archive-before-withdrawal, rollback, and no-traffic-change gates.

## Safety boundary

No DNS, Unbound, RPZ, nftables, firewall, Fail2ban enforcement, routing, proxying, IDS rules, reputation lists, authentication, certificates, public or restricted routes, production traffic, timer scheduling, `/var/www` publication or removal, operational alert feed, `Actual` alert acceptance, call/page origination, alert-tone transmission, DTMF transmission, carrier routing, source pruning, or data deletion changed as part of the accepted alerting and DTMF read-only work.
