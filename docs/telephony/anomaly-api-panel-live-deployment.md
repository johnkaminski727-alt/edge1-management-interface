# Telephony Anomaly API and Panel Live Deployment

## Purpose

This runbook deploys the accepted informational anomaly API into the existing loopback analytics service and verifies delivery through the private telephony console.

The deployment moves `wwcx-telephony-analytics.service` from its previously accepted feature-worktree source to canonical `/opt/edge1-management-interface` and restarts that service once. The console service is not restarted because:

- its Python server already executes from the canonical repository;
- the existing three-route proxy map is unchanged;
- static HTML, JavaScript, and CSS files are served directly from the canonical checkout.

## Mutation scope

The only authorized runtime mutations in this procedure are:

1. replace `/etc/systemd/system/wwcx-telephony-analytics.service` with the repository unit rendered for the canonical checkout;
2. run `systemctl daemon-reload`;
3. restart `wwcx-telephony-analytics.service`.

The procedure does not restart `wwcx-telephony-console.service`. It does not change Asterisk, FreePBX, PJSIP, carriers, routes, DIDs, dial plans, messages, DTMF, databases, credentials, listeners, firewall rules, DNS, certificates, authentication, or public exposure.

## Pre-deployment gates

The deployment script fails before mutation unless all of the following are true:

- the host is `edge1.ww.cx`;
- execution is through `sudo`;
- the canonical repository exists and is owned consistently;
- `.git/index` is owned by the repository owner and no index lock exists;
- the repository is on clean `main`;
- the operator-supplied accepted merge is an ancestor of `HEAD`;
- repository anomaly, API, console, and deployment validations pass;
- the console service is active and executes from canonical main;
- ports `8096` and `8099` are not exposed on wildcard listeners;
- the console already serves the anomaly card, JavaScript, and stylesheet;
- the current analytics unit is a regular file and the service is active and enabled;
- a complete rollback copy of the prior analytics unit has been captured.

Git inspection in the root-run scripts is executed as the repository owner with `GIT_OPTIONAL_LOCKS=0`; the root process never runs a writable Git status command against the repository index.

## Automatic rollback

Immediately before the first mutation, the script installs an `ERR` trap.

If unit installation, daemon reload, restart, endpoint validation, source-provenance validation, console delivery, privacy checks, or final repository checks fail, the script:

1. restores the exact prior analytics unit from the protected evidence directory;
2. runs `systemctl daemon-reload`;
3. restarts the analytics service through its prior command and worktree;
4. verifies the prior `/healthz` endpoint when possible;
5. records rollback service properties and the triggering exit code.

The script never resets, cleans, stashes, rewrites, or deletes repository work to obtain a clean state.

## Live acceptance

After the analytics restart succeeds, the read-only audit verifies:

- analytics and console services are active;
- analytics remains enabled at boot;
- analytics runs as `wwadmin` from canonical main;
- API, platform, and anomaly evaluator runtime hashes match the canonical repository;
- listeners on `8096` and `8099` remain loopback-only;
- `/healthz`, health, anomaly, call-summary, and interconnect-summary endpoints return valid JSON;
- POST remains rejected with HTTP `405`;
- the dedicated anomaly payload has the fixed six-indicator, no-action contract;
- the nested anomaly payload matches the dedicated endpoint;
- the console same-origin health response carries the same anomaly contract;
- the console serves the anomaly card, JavaScript, and stylesheet;
- browser assets contain no direct port-`8099` access;
- payload privacy validation passes;
- `.git/index` ownership remains unchanged;
- the repository remains clean.

## Evidence locations

Deployment evidence:

```text
/var/lib/wwcx-deployment-evidence/telephony-anomaly-api-panel-deployment/<UTC timestamp>
```

Read-only live-acceptance evidence:

```text
/var/lib/wwcx-deployment-evidence/telephony-anomaly-api-panel-live-acceptance/<UTC timestamp>
```

Each directory receives a SHA-256 file inventory and manifest hash.

## Invocation

After the deployment PR is merged and canonical `main` is synchronized:

```bash
TS="$(date -u +%Y%m%dT%H%M%SZ)"
sudo bash deploy/telephony/telephony-anomaly-api-panel-deploy.sh \
  --required-commit "<merged deployment commit>" \
  --evidence-dir "/var/lib/wwcx-deployment-evidence/telephony-anomaly-api-panel-deployment/$TS"
```

## No telephony traffic

Successful execution does not originate a call or message, transmit DTMF, access a carrier account, change a route, inspect a production CDR database, or perform an emergency-calling test. The anomaly output remains informational and cannot notify, enforce, block, reroute, or control a service.
