# Telephony Anomaly Console Refresh Correction

## 2026-08-01 live finding

The first bounded anomaly deployment correctly moved the analytics service to canonical `main`, but the final live acceptance audit received HTTP 404 from:

```text
http://127.0.0.1:8096/api/telephony/analytics/health
```

The repository copy of `server/telephony_status_server.py` already contained that fixed proxy route. The running `wwcx-telephony-console.service` process had started before the route was merged and therefore retained a stale in-memory route map. Static HTML, JavaScript, and CSS were current because they are read from disk on each request, but Python route definitions required a console restart.

The analytics deployment automatically restored the exact prior unit and worktree after the failed acceptance audit. Both services remained active, both listeners remained loopback-only, `.git/index` ownership remained `wwadmin:wwadmin`, and no traffic or routing action occurred.

## Corrected deployment sequence

`deploy/telephony/telephony-anomaly-api-panel-deploy-v2.sh` performs the missing bounded console refresh before delegating to the accepted analytics deployment engine:

1. verify `edge1.ww.cx`, root execution, clean canonical `main`, accepted commit ancestry, and repository-index ownership;
2. capture console service properties, PID, listener state, and the pre-refresh proxy response;
3. restart only `wwcx-telephony-console.service`;
4. require a new PID, healthy loopback listener, canonical source path, HTTP 200 from the same-origin analytics health route, valid JSON, and delivery of the anomaly panel assets;
5. invoke `telephony-anomaly-api-panel-deploy.sh`, which retains its exact analytics-unit rollback behavior;
6. rerun final console proxy, service, repository, and evidence-manifest checks.

If the wrapper fails after beginning the console refresh, it attempts one bounded console recovery restart and records the resulting service health. If the delegated analytics deployment fails, that script independently restores the exact prior analytics unit and runtime before returning failure.

## Runtime mutation boundary

The corrected procedure permits only:

- one console service restart to load the already-merged canonical Python route map;
- analytics unit replacement with the accepted canonical unit;
- `systemctl daemon-reload`;
- analytics service restart;
- a console recovery restart only after an error.

It does not change listener addresses, firewall rules, DNS, certificates, authentication, Asterisk, FreePBX, PJSIP, carriers, DIDs, dial plans, databases, credentials, or public exposure.

## Safety boundary

Both services must remain on `127.0.0.1` ports `8096` and `8099`. The APIs remain read-only and informational. No calls, messages, DTMF transmissions, route changes, notification dispatch, or traffic enforcement are performed.

## Evidence

The wrapper uses one parent evidence directory with separated console and analytics records:

```text
/var/lib/wwcx-deployment-evidence/telephony-anomaly-api-panel-deployment/<UTC timestamp>/
  console-refresh/
  analytics-deployment/
```

The parent directory receives a recursive SHA-256 inventory and manifest hash. The delegated analytics deployment continues to create its separate read-only live-acceptance evidence directory.
