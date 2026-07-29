# Network Defense observability deployment

## Scope

This procedure deploys the read-only Network Defense exporter, timer, Operations Center navigation, Security Correlation page, and Network Defense console.

It does not:

- install or modify Unbound configuration;
- stage or activate an RPZ policy;
- reload or restart a DNS resolver;
- alter DNS answers;
- change firewall, proxy, routing, Fail2ban, or IDS controls.

## Prerequisites

- Host: Edge1.
- Repository: `/opt/edge1-management-interface`.
- Branch: `main`.
- Working tree: clean.
- Required DNS Defense merge is present in history.
- Root access is available for systemd and `/var/www/edge1-status` installation.

## Deployment

```bash
cd /opt/edge1-management-interface
git fetch origin
git switch main
git pull --ff-only origin main
sudo ./deploy/install-network-defense-observability.sh
```

The installer validates repository code before changing the host. It then:

1. records the repository revision and prior timer state;
2. backs up affected unit, HTML, legacy status, and scoped data paths;
3. publishes the Operations Center, Security Correlation, and Network Defense pages;
4. creates the root-owned `/var/www/edge1-status/network-defense/data` publication directory;
5. installs `wwcx-network-defense.service` and `wwcx-network-defense.timer`;
6. enables the timer and runs the exporter once;
7. verifies the generated JSON safety contract and local HTTP pages;
8. records hashes, unit state, and recent service logs.

The service can write only inside the scoped `network-defense/data` directory. It retains an empty capability set and cannot write to the shared `/var/www/edge1-status` root.

If a deployment or verification command fails after mutation begins, the installer captures service diagnostics and restores the saved files and prior timer enablement/active state.

## Evidence

Default location:

```text
/var/lib/wwcx-deployment-evidence/network-defense/<UTC timestamp>/
```

The final terminal output prints the exact evidence directory.

## Expected state

The Network Defense snapshot must report:

```json
{
  "traffic_controls_changed": false,
  "dns_policy": {
    "enforcement_enabled": false,
    "enforcement_verified": false,
    "traffic_controls_changed": false,
    "requires_explicit_activation": true
  }
}
```

A missing staged DNS policy is represented as `not_staged`; it is not a deployment failure. Resolver enforcement remains a separate privileged change requiring exact authorization.

## Manual verification

```bash
systemctl is-enabled wwcx-network-defense.timer
systemctl is-active wwcx-network-defense.timer
systemctl show wwcx-network-defense.service -p Result -p ExecMainStatus
curl -fsS http://127.0.0.1/edge1-status/network-defense/data/network-defense.json | python3 -m json.tool
curl -fsS http://127.0.0.1/edge1-status/network-defense/ >/dev/null
```
