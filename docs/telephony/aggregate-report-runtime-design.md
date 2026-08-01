# Telephony Aggregate Report Runtime Design

## Design-only policy

This is a **design-only, disabled-by-default** runtime plan. It defines protected paths, owner-only permissions, retention parameters, audit-chain gates, and fail-closed systemd templates without creating or changing anything on Edge1.

## Fixed protected paths

The proposed runtime root is:

```text
/var/lib/wwcx-telephony-analytics-reports
```

Proposed children:

```text
incoming/current.json
reports/
audit/report-events.jsonl
```

Proposed deployment evidence root:

```text
/var/lib/wwcx-deployment-evidence/telephony-analytics-report-runtime
```

All runtime directories are designed for mode `0700`; all input, report, manifest, and audit files are designed for mode `0600`; and the proposed service umask is `0077`.

## Missing activation sentinel

The design requires this separate activation sentinel:

```text
/etc/wwcx-telephony/analytics-report-runtime-enabled
```

The repository does not create that sentinel. Both systemd design templates use `ConditionPathExists` for it. They also require an executable runner that is intentionally absent:

```text
/opt/edge1-management-interface/tools/telephony/run_telephony_aggregate_report.py
```

The policy therefore records `enabled=false`, `deployment_authorized=false`, and `runner_implemented=false`.

## Systemd design templates

The templates live under `design/telephony/systemd/`, not the installable systemd directory. They have no `[Install]` section. The timer is non-persistent and proposes one UTC run at `02:15` with up to fifteen minutes of randomized delay. The service permits only `AF_UNIX`, uses owner-only output, and is restricted to the proposed report and evidence roots.

These templates are evidence of the reviewed boundary only. They are not installed, enabled, started, or accepted for live use.

## Already-aggregated input only

The proposed incoming file must conform to the accepted aggregate-report input contract. The design does not collect from the analytics API, CDR files, AMI/ARI, SIP edge, logs, packets, databases, carriers, or any other live source.

## Audit append gate

The offline generator emits `report-audit-input.json`, but the runtime design keeps both `append_enabled=false` and `automatic_append=false`. A future runner would have to verify the complete existing hash chain before any separately authorized append. This increment creates no audit log and appends no event.

## Retention design

Retention is disabled. The proposed review values are:

- incoming aggregate snapshot: 7 days;
- generated report bundles: 90 days;
- minimum free-space gate: 1 GiB;
- mandatory dry-run before any deletion;
- never delete an unmanifested bundle;
- never prune audit events;
- retain the audit chain until a separately authorized checkpoint exists.

No deletion implementation or authorization is included.

## Read-only planner

The planner validates the exact policy and prints a deterministic JSON plan:

```bash
python3 tools/telephony/plan_telephony_report_runtime.py
```

The expected status is:

```text
blocked_pending_separate_authorization_and_runner
```

The planner performs no filesystem, systemd, network, audit, or retention mutation.

## No runtime activation

No service, timer, directory, sentinel, audit log, report job, or retention action is created by this design.

## Deployment gate

Before a future deployment can be considered, all of the following require a separate implementation and live review:

1. a minimal runner that creates a unique output directory and refuses stale or malformed input;
2. protected runtime and evidence directory creation with ownership verification;
3. explicit handling of the incoming aggregate snapshot without adding a live collector;
4. full report and audit-candidate validation before any audit append;
5. retention dry-run evidence and a non-destructive default;
6. rollback for units, policy, directories, and scheduler state;
7. confirmation that the activation sentinel is intentionally created;
8. separate authorization for installation, timer enablement, audit append, and retention deletion.
