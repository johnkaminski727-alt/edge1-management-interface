# Current State

Last verified: 2026-07-31  
Repository: `johnkaminski727-alt/edge1-management-interface`  
Authoritative branch: `main`  
Accepted Edge1 live revision: `a06f035e7fcf933a03ec752c66ce0261c5a65ba7`  
Latest repository implementation merge: `7456304d41063075be15ff894af815877dd8a554`

## Verified live baseline

- Security Correlation and Network Defense are live and accepted.
- Suricata drill-down, caching, normalization, and enrichment are live.
- Network Defense applies the accepted network-source freshness threshold of `600` seconds.
- Overall Network Defense state is `limited`.
- DNS remains `not_staged`; DNS enforcement is false.
- Verified enforcement count remained `1` before and after freshness activation.
- Traffic controls and Network Defense timer state remained unchanged.
- Asterisk was directly observed running version `22.8.2` with PJSIP, `app_senddtmf`, `app_playtones`, and DSP loaded; no CAP-CP/EBS-specific dialplan or configured PJSIP endpoint was observed.
- The interrupted inline Asterisk update reached `apt-get update` only. No package installation or PBX restart was evidenced, so the live version must be rechecked before any update claim.

Protected live evidence:

```text
/var/lib/wwcx-deployment-evidence/edge1-project-completion-preflight/20260730T193415Z
/var/lib/wwcx-deployment-evidence/network-defense-freshness/20260730T195031Z
/var/lib/wwcx-deployment-evidence/asterisk-security-update/20260731T231305Z
```

## Completed repository programs

- Protected Suricata retention runtime and closeout: PRs #138-139.
- Minimized public-summary route, CSP, staging runtime, and closeout: PRs #140-145.
- Authenticated detailed-operations browser/session boundary and closeout: PRs #146-147.
- Restricted-artifact migration manifest and closeout: PRs #148-149.
- Security-boundary live inventory bundle merged through PR #151 as `85d9a9cb43e5ca4dd09f2d955b00997ef28e2cf0`.
- Test-only EBS and CAP-CP compatibility foundation merged through PR #157 as `7456304d41063075be15ff894af815877dd8a554`.

No public-summary staging, authenticated restricted route, restricted release, detailed-artifact migration, public cutover, detailed-artifact removal, protected-retention installation, CAP feed connection, alert origination, alert-tone transmission, Asterisk alert dialplan, or public alert distribution has occurred on Edge1.

## Security-boundary live inventory repository completion

The authenticated read-only host-evidence bundle is implemented and merged.

Assets:

- `config/security/edge1-security-completion-authorization-20260730.json`;
- `tools/security/edge1-security-boundary-live-inventory.sh`;
- `tools/security/reconcile-edge1-live-inventory.py`;
- `tools/security/redact-edge1-boundary-text.py`;
- `tests/test_edge1_security_boundary_live_inventory.py`;
- runbook, validation checklist, register, and continuity records.

Exact implementation head `4a18c05f2a6f31369a3abfa695330ac5bf39d40a` passed:

- `Validate repository` run 662;
- `Edge1 Operator Validation` run 494;
- 11 changed files;
- zero commits behind `main`;
- mergeable state;
- zero unresolved review threads;
- merge through PR #151 as `85d9a9cb43e5ca4dd09f2d955b00997ef28e2cf0`.

The bundle records exact public-tree hashes and modes, filesystem anomalies, manifest reconciliation, Apache/module readiness, redacted service definitions, anonymous route/header observations, listeners, capacity, candidate roots, audit metadata, retention metadata, and an evidence SHA-256 manifest. It does not collect credentials, secret values, cookie values, environment dumps, SSH material, private keys, password-file contents, or audit-log contents.

## Alerting compatibility repository completion

The repository now includes a bounded receive-side and offline-test foundation for CAP 1.2/CAP-CP and the retired EBS 853/960 Hz attention signal.

Assets:

- `tools/alerting/capcp_probe.py`;
- `tools/alerting/capcp_lifecycle_probe.py`;
- `tools/alerting/ebs_tone_probe.py`;
- `tools/alerting/asterisk_alerting_readiness.sh`;
- `deploy/alerting/install-alerting-lab.sh`;
- `deploy/telephony/asterisk22-guarded-update.sh`;
- `config/alerting/wwcx-alerting-lab-policy.json`;
- alerting fixtures, tests, CI validation entrypoint, and operator runbook.

Exact implementation head `bafdc354a52099a2fb64ab9f4967525d7a7be557` passed:

- `Validate repository` run 692;
- `Edge1 Operator Validation` run 524;
- `WW.CX interconnect staging validation` run 50;
- 9 targeted alerting compatibility tests;
- POSIX shell, Python compilation, JSON, and repository-wide validation;
- zero unresolved review threads;
- merge through PR #157 as `7456304d41063075be15ff894af815877dd8a554`.

The implementation blocks `Actual` alerts by default and creates no CAP source, network listener, SIP/PSTN delivery path, call origination, tone generation, Asterisk dialplan, Kamailio route, firewall rule, certificate, or public claim of Alert Ready, NPAS, EAS, or EBS certification.

## Live execution state

The security inventory script and the merged alerting tools have not been executed on Edge1 from this runtime. No new protected inventory, alerting-lab installation, Asterisk package update, PBX restart, CAP feed, alert route, call, page, or tone transmission is claimed live.

## Alerting next gates

1. update the Edge1 checkout to merged `main` and confirm a clean working tree;
2. run the read-only Asterisk alerting readiness audit;
3. run the guarded Asterisk package simulation and review the exact candidate and removals list;
4. apply the Asterisk update only with zero active calls and preserved rollback evidence;
5. run the offline alerting-lab installer dry-run, then optionally install the offline tools without enabling a service or listener;
6. keep any CAP source, `Actual` alert handling, Asterisk adapter, alert delivery, or public compatibility claim behind separate governance and production authorization.

## Security next gates

1. run the merged inventory on a clean authenticated Edge1 `main` checkout;
2. review unknown, missing, prefix-contained, duplicate, stale, historical, and operator-maintained artifacts;
3. verify an actually available approved identity-provider/Apache adapter path;
4. construct restricted and public staging installers from measured host evidence;
5. preserve authentication-first, archive-before-withdrawal, rollback, and no-traffic-change gates.

## Safety boundary

No DNS, Unbound, RPZ, nftables, firewall, Fail2ban enforcement, routing, proxying, IDS rules, reputation lists, authentication, certificates, listeners, public or restricted routes, production traffic, timer scheduling, `/var/www` publication or removal, alert feed, call origination, alert-tone transmission, release activation, source pruning, or data deletion changed.
