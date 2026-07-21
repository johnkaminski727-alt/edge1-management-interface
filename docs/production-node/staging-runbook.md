# Production Node Staging Runbook

## Purpose

This package establishes a passive production-candidate node without authorizing live traffic or privileged production changes.

## Safety boundary

The example manifest requires all production-impact flags to remain `false`. Promotion to canary or active service is a separate controlled change covering routing, DNS, certificates, authentication, carrier trunks, emergency calling, number portability, signing authority, and authoritative writes.

## Lifecycle

`provisioning -> isolated -> validated -> production-candidate -> canary -> active -> draining -> retired`

Only the first four states are in scope for routine staging work. Canary and active transitions require an approved change window and a tested rollback path.

## Repository validation

```bash
python3 deploy/production-node/validate-manifest.py
python3 tests/validate_production_node_staging.py
```

## Candidate-host preflight

Copy the repository to the candidate host, customize a private manifest outside the public repository, and run:

```bash
EVIDENCE_DIR=/var/lib/wwcx/production-node/evidence/preflight \
  deploy/production-node/validate-host.sh /path/to/node-manifest.json
```

The preflight records host facts, required-command discovery, listeners, and failed systemd units. It does not install packages, change firewall policy, restart services, or enable traffic.

## Required evidence before promotion

- immutable release or commit identifier;
- validated node manifest;
- host preflight output;
- service syntax and health checks;
- listener inventory reviewed against policy;
- monitoring and alert delivery verified;
- backup and restore test evidence;
- reboot persistence test;
- rollback procedure and objective rollback triggers;
- explicit approval for any canary or active traffic.

## Rollback posture

Before traffic introduction, keep the current production node available and preserve the previous application and configuration release. A candidate can always be returned to `isolated` by removing it from upstream selection and disabling production-impact integrations.
