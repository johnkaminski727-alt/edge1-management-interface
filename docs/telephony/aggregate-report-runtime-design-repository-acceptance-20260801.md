# Telephony Aggregate Report Runtime Design Repository Acceptance — 2026-08-01

## Decision

Accepted at repository level as a non-mutating, fail-closed design for a future protected report runtime.

## Design-only policy

The canonical policy is fixed at `mode=design_only`, `enabled=false`, `deployment_authorized=false`, and `runner_implemented=false`. The read-only planner renders `blocked_pending_separate_authorization_and_runner` and reports `mutations_performed=false`.

## Fixed protected paths and permissions

The design fixes one owner-only runtime root, one protected evidence root, a single incoming aggregate JSON path, a report-bundle directory, and an append-only audit-log candidate. Proposed directories use mode `0700`, files use `0600`, and the service umask is `0077`.

## Missing activation sentinel

The systemd templates require `/etc/wwcx-telephony/analytics-report-runtime-enabled`. The repository does not create it. They also require an intentionally absent runner. Both templates remain under `design/`, contain no `[Install]` section, and are not deployment assets.

## Audit append gate

Automatic audit append is false. Audit pruning is false. A future append must verify the full existing chain and requires separate authorization.

## Retention design

Retention is disabled, requires a future dry-run, refuses deletion of unmanifested bundles, and preserves the chain until a separately authorized checkpoint.

## No runtime activation

This acceptance does not create a runtime or evidence directory, incoming file, report, audit log, activation sentinel, service, timer, cron job, retention job, or audit event. It does not install, enable, start, restart, or reload anything.

## Safety boundary

No live source, network request, database query, credential, customer record, PBX action, carrier action, call, message, DTMF transmission, route change, notification, traffic enforcement, firewall, DNS, certificate, authentication, public listener, or data deletion is introduced.

A future runner, installer, activation sentinel, scheduler, audit append, and retention action remain separately implemented, reviewed, authorized, deployed, and live-accepted work.
