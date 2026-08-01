# Telephony Anomaly API and Panel Live Deployment

## Purpose

This runbook deploys the accepted informational anomaly API into the existing loopback analytics service and verifies delivery through the private telephony console.

## Corrected operator entrypoint

The authoritative operator entrypoint is now:

```text
deploy/telephony/telephony-anomaly-api-panel-deploy-v2.sh
```

The original `telephony-anomaly-api-panel-deploy.sh` remains the internal rollback-capable analytics deployment engine. It must not be used alone for this release because the console Python process must first be restarted to load the already-merged proxy route.

## 2026-08-01 live correction

The first live attempt proved that static console assets were current but the long-running console process retained an older in-memory route map. The live acceptance audit received HTTP 404 from `/api/telephony/analytics/health`. The analytics rollback completed successfully, restoring the exact prior unit and worktree.

The corrected procedure therefore restarts `wwcx-telephony-console.service` once before the analytics deployment. See `anomaly-api-panel-console-refresh.md` for the complete finding and evidence model.

## Mutation scope

The authorized runtime mutations are:

1. restart `wwcx-telephony-console.service` so canonical Python route definitions are loaded;
2. replace `/etc/systemd/system/wwcx-telephony-analytics.service` with the repository unit rendered for canonical `main`;
3. run `systemctl daemon-reload`;
4. restart `wwcx-telephony-analytics.service`;
5. perform one bounded console recovery restart only if the wrapper encounters an error.

The procedure does not change Asterisk, FreePBX, PJSIP, carriers, routes, DIDs, dial plans, messages, DTMF, databases, credentials, listener addresses, firewall rules, DNS, certificates, authentication, or public exposure.

## Pre-deployment gates

The v2 wrapper and delegated analytics engine fail unless all relevant checks pass:

- host is `edge1.ww.cx` and execution is through `sudo`;
- canonical repository exists and ownership is consistent;
- `.git/index` is owned by the repository owner and no index lock exists;
- repository is on clean `main`;
- operator-supplied accepted merge is an ancestor of `HEAD`;
- repository anomaly, API, console, deployment, and console-refresh validations pass;
- console and analytics services are active before mutation;
- console executes from canonical `/opt/edge1-management-interface`;
- ports `8096` and `8099` are loopback-only;
- a complete rollback copy of the prior analytics unit is captured.

Git inspection in root-run scripts is executed as the repository owner with `GIT_OPTIONAL_LOCKS=0`.

## Console refresh verification

After the console restart, the wrapper requires:

- a new nonzero console PID;
- active service state and canonical source path;
- loopback-only listener on port `8096`;
- HTTP 200 and valid JSON from `/api/telephony/analytics/health`;
- anomaly card, JavaScript, and stylesheet delivery from canonical `main`.

## Automatic analytics rollback

Immediately before analytics mutation, the delegated script installs an `ERR` trap.

If unit installation, daemon reload, analytics restart, endpoint validation, source-provenance validation, console delivery, privacy checks, or final repository checks fail, it:

1. restores the exact prior analytics unit from protected evidence;
2. runs `systemctl daemon-reload`;
3. restarts analytics through its prior command and worktree;
4. verifies the prior `/healthz` endpoint when possible;
5. records service properties and the triggering exit code.

The wrapper separately attempts one console recovery restart if an error occurs after the console refresh begins.

## Live acceptance

The read-only audit verifies:

- analytics and console services are active;
- analytics remains enabled at boot;
- analytics runs as `wwadmin` from canonical `main`;
- API, platform, and anomaly evaluator runtime hashes match the canonical repository;
- listeners on `8096` and `8099` remain loopback-only;
- health, anomaly, call-summary, and interconnect-summary endpoints return valid JSON;
- POST remains rejected with HTTP `405`;
- dedicated, nested, and console same-origin anomaly contracts agree;
- console serves the anomaly card and browser assets without direct port-`8099` access;
- payload privacy validation passes;
- `.git/index` ownership remains unchanged and the repository remains clean.

## Evidence locations

Parent deployment evidence:

```text
/var/lib/wwcx-deployment-evidence/telephony-anomaly-api-panel-deployment/<UTC timestamp>/
  console-refresh/
  analytics-deployment/
```

Read-only live-acceptance evidence:

```text
/var/lib/wwcx-deployment-evidence/telephony-anomaly-api-panel-live-acceptance/<UTC timestamp>
```

Each evidence set receives SHA-256 inventories and manifest hashes.

## Invocation

After the corrective PR is merged and canonical `main` is synchronized:

```bash
TS="$(date -u +%Y%m%dT%H%M%SZ)"
sudo bash deploy/telephony/telephony-anomaly-api-panel-deploy-v2.sh \
  --required-commit "<merged corrective commit>" \
  --evidence-dir "/var/lib/wwcx-deployment-evidence/telephony-anomaly-api-panel-deployment/$TS"
```

## No telephony traffic

Successful execution does not originate a call or message, transmit DTMF, access a carrier account, change a route, inspect a production CDR database, or perform an emergency-calling test. The anomaly output remains informational and cannot notify, enforce, block, reroute, or control a service.
