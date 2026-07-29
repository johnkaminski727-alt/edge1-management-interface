# Security Correlation observability deployment

## Scope

This procedure deploys the read-only Security Correlation exporter, one-minute timer, and browser console on Edge1.

It does not:

- reload or modify Suricata;
- install or modify Unbound or DNS policy;
- change firewall, Fail2ban, proxy, routing, or reputation-filter controls;
- capture packets or publish raw logs;
- create any write-capable browser or API action.

## Prerequisites

- Host: `edge1.ww.cx`.
- Repository: `/opt/edge1-management-interface`.
- Branch: `main`.
- Working tree: clean.
- Required Security Correlation foundation commit is present in history.
- Root access is available for systemd and status publication.

## Deployment

```bash
cd /opt/edge1-management-interface
git fetch origin
git switch main
git pull --ff-only origin main
sudo bash ./deploy/install-security-correlation-observability.sh
```

The installer:

1. validates branch, working tree, required history, Python, JavaScript, shell, and unit contracts;
2. records the repository revision and prior timer state;
3. backs up the service, timer, console, scoped data directory, and compatibility read path;
4. creates `/var/www/edge1-status/security/correlation/data` as `root:root` mode `0755`;
5. installs the hardened service and timer;
6. publishes the console and an installer-managed compatibility symlink at `/var/www/edge1-status/security-correlation.json`;
7. starts the exporter and verifies its privacy/read-only contract;
8. verifies the local console and JSON endpoint;
9. records hashes, unit state, and recent journal evidence.

If any live step fails, the installer captures failure diagnostics and restores all backed-up paths and the prior timer state.

## Expected success output

```text
Security Correlation observability deployment passed.
Evidence: /var/lib/wwcx-deployment-evidence/security-correlation/<UTC timestamp>
No IDS, DNS, firewall, proxy, routing, Fail2ban, or reputation-filter controls were changed.
```

## Evidence

Default location:

```text
/var/lib/wwcx-deployment-evidence/security-correlation/<UTC timestamp>/
```

Expected evidence includes:

- repository revision and pre-deployment Git status;
- repository validation output;
- service and timer status;
- recent service journal;
- generated correlation JSON;
- local console HTML;
- compatibility symlink target;
- SHA-256 hashes;
- rollback or success result.

## Manual verification

```bash
systemctl is-enabled wwcx-security-correlation.timer
systemctl is-active wwcx-security-correlation.timer
systemctl show wwcx-security-correlation.service -p Result -p ExecMainStatus
readlink /var/www/edge1-status/security-correlation.json
curl -fsS http://127.0.0.1/edge1-status/security-correlation.json | python3 -m json.tool
curl -fsS http://127.0.0.1/edge1-status/security/correlation.html >/dev/null
```

The snapshot may legitimately report source warnings when optional telemetry is absent. Missing optional inputs are not a deployment failure.
