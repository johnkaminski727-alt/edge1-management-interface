# Security observability live acceptance

## Purpose

This procedure proves that the deployed Security Correlation exporter is healthy, fresh, available through its compatibility endpoint, and consumed by the live Network Defense snapshot.

It is a read-only verification step. It does not start, stop, restart, reload, enable, or modify any service or traffic control.

## Prerequisites

- Network Defense observability is deployed.
- Security Correlation observability is deployed with the bounded installer.
- Both timers have had enough time to refresh their one-shot exporters. The normal interval is one minute.
- Repository `main` is pulled on Edge1.

## Verification

After Security Correlation deployment, allow up to two minutes for the Network Defense timer to consume the new correlation snapshot, then run:

```bash
cd /opt/edge1-management-interface
git pull --ff-only origin main
sudo bash ./tools/security/verify-security-observability-live.sh
```

The verifier records protected evidence under:

```text
/var/lib/wwcx-deployment-evidence/security-observability-acceptance/<UTC timestamp>/
```

## Acceptance checks

The verifier requires:

- `wwcx-security-correlation.timer` enabled and active;
- `wwcx-network-defense.timer` enabled and active;
- both one-shot services to report `Result=success` and `ExecMainStatus=0`;
- the correlation compatibility symlink to target the scoped root-owned data file;
- successful local HTTP reads of both consoles and JSON endpoints;
- correlation JSON with `read_only: true`, minimized event fields, and no payload, credential, key, or raw-log inclusion;
- Network Defense JSON with `traffic_controls_changed: false`;
- DNS enforcement fields remaining false and explicit activation still required;
- Network Defense source `correlation` available and not stale;
- both snapshots fresh within ten minutes by default.

The freshness limit can be narrowed for investigation:

```bash
sudo SECURITY_OBSERVABILITY_MAX_AGE_SECONDS=180 \
  bash ./tools/security/verify-security-observability-live.sh
```

## Expected success

```text
Security observability acceptance passed.
Evidence: /var/lib/wwcx-deployment-evidence/security-observability-acceptance/<UTC timestamp>
Security Correlation is live and consumed by Network Defense. No traffic controls were changed.
```

## Failure behavior

A failed check makes no runtime change. It captures:

- current service and timer status;
- recent Security Correlation journal entries;
- recent Network Defense journal entries;
- any endpoint documents fetched before the failure;
- repository revision and Git status;
- an `accepted=false` result record.

When the only failure is that Network Defense has not consumed correlation yet, wait for the next timer interval and rerun the verifier. Do not restart or alter network controls to satisfy acceptance.

## Safety boundary

This verifier contains no commands that modify:

- Suricata or IDS configuration;
- Unbound, DNS policy, or DNS answers;
- nftables or other firewall rules;
- Fail2ban jails;
- proxy, routing, or reputation-filter controls;
- public listeners or production traffic.
