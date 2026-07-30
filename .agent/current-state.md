# Current State

Last verified: 2026-07-30  
Repository: `johnkaminski727-alt/edge1-management-interface`  
Authoritative branch: `main`  
Accepted Edge1 live revision: `a06f035e7fcf933a03ec752c66ce0261c5a65ba7`  
Latest repository closeout: `d236219067c78c584b06c11a5612c5ed28ef72fb`  
Active repository branch: `ops/edge1-security-boundary-live-inventory-20260730`

## Verified live baseline

- Security Correlation and Network Defense are live and accepted.
- Suricata drill-down, caching, normalization, and enrichment are live.
- Network Defense applies the accepted network-source freshness threshold of `600` seconds.
- Overall Network Defense state is `limited`.
- DNS remains `not_staged`; DNS enforcement is false.
- Verified enforcement count remained `1` before and after freshness activation.
- Traffic controls and Network Defense timer state remained unchanged.

Protected live evidence:

```text
/var/lib/wwcx-deployment-evidence/edge1-project-completion-preflight/20260730T193415Z
/var/lib/wwcx-deployment-evidence/network-defense-freshness/20260730T195031Z
```

## Completed repository programs

- Protected Suricata retention runtime and closeout: PRs #138-139.
- Minimized public-summary route, CSP, staging runtime, and closeout: PRs #140-145.
- Authenticated detailed-operations browser/session boundary and closeout: PRs #146-147.
- Restricted-artifact migration manifest and closeout: PRs #148-149.
- Latest repository closeout: `d236219067c78c584b06c11a5612c5ed28ef72fb`.

No public-summary staging, authenticated restricted route, restricted release, detailed-artifact migration, public cutover, detailed-artifact removal, or protected-retention installation has occurred on Edge1.

## Security-boundary live inventory phase

A focused read-only host-evidence bundle is implemented on `ops/edge1-security-boundary-live-inventory-20260730`.

Implemented:

- machine-readable record of the user's explicit authorization for the four named security-completion programs;
- root-run, clean-`main` inventory guard;
- protected timestamped evidence directory;
- exact JSON path/SHA-256/mode/byte inventory of `/var/www/edge1-status`;
- symlink and non-regular-file anomaly reporting;
- automatic reconciliation against the merged restricted-artifact manifest and access policy;
- Apache syntax, vhost, module, config-hash, and directive-name-only readiness evidence;
- redacted systemd unit and service-state evidence;
- local/public anonymous route and security-header matrix;
- listener, capacity, candidate-root, audit-log-metadata, and retention-tree inventories;
- explicit no-credential, no-cookie-value, no-source-mutation, no-traffic-change results;
- unit, redaction, static non-mutation, and synthetic reconciliation tests;
- runbook and audit register.

The bundle records no Git remote URLs, environment dump, SSH material, private keys, shadow data, password-file contents, provider/client secret values, cookie values, or audit-log contents.

## Repository validation state

Exact-head CI, changed-file review, zero-behind review, mergeability, and review-thread checks are pending.

## Live execution state

No authenticated Edge1 execution path is available in the current authoring runtime. The new inventory script has not been executed on Edge1 and no new protected evidence directory is claimed.

## Next gates

1. pass exact-head repository workflows and merge the inventory bundle;
2. run the merged inventory on a clean authenticated Edge1 `main` checkout;
3. review unknown, missing, prefix-contained, duplicate, stale, historical, and operator-maintained artifacts;
4. select only an actually available approved identity-provider/Apache adapter path;
5. construct restricted and public staging installers from the measured host evidence;
6. preserve authentication-first, archive-before-withdrawal, rollback, and no-traffic-change gates.

## Safety boundary

No DNS, Unbound, RPZ, nftables, firewall, Fail2ban enforcement, routing, proxying, IDS rules, reputation lists, authentication, certificates, listeners, public or restricted routes, production traffic, timer scheduling, `/var/www` publication or removal, release creation, source mutation, pruning, or data deletion changed.
