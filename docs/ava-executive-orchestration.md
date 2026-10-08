# AVA Executive Orchestration Layer

## Purpose

AVA is the executive coordinator for Edge1 automation. Bots remain bounded workers with their existing service identities, credentials, source policies and mutation gates. AVA coordinates work; she does not receive generic root or unrestricted execution authority.

## Control model

Events and timers wake the AVA Executive Orchestrator. It reconciles the Automation Center inventory into the durable Ava Office database, registers each custom bot as a team member, records check-ins, creates one durable attention work item per continuing affected team member, and accepts native bot reports from the direct-report inbox.

The existing Ava Office Manager policy remains authoritative for generic action planning. Unknown capabilities fail closed. Financial, legal, contract, credential, destructive and emergency capabilities remain behind restricted or explicit confirmation paths.

## Team model

Each team member records: member ID, display name, department, role, systemd service/timer identity, action level, authority ceiling, health state, last check-in, and capabilities. Current departments include Automation & Operations, Security, Records & Library, Contacts & Relationships, Finance, Communications, Recovery & Continuity, Infrastructure & Network, and Business & Web Operations.

Action levels map conservatively to executive authority ceilings: READ-ONLY to observe, AUTO-STAGE and REVIEW-REQUIRED to prepare, and AUTO-FIX to routine. This is a ceiling, not permission to bypass the bot's own control plane.

## Assignments and reports

AVA stores executive assignments separately from the underlying Office work item. An assignment identifies the responsible bot, objective, state, priority, dependencies and requester. Reports retain bot identity, assignment link when applicable, health state, summary, bounded detail, attention flag, severity, source reference and timestamp.

Continuing unhealthy conditions use a stable `ava-attention:<member_id>` work key, so repeated check-ins update history without creating duplicate open work.

## Native direct-report contract

A bot may write a JSON object into `/var/lib/wwcx-ava-office-manager/report-inbox/`. The file must be readable by the `wwadmin` AVA Executive service. Supported fields are:

- `member_id` (required)
- `report_type`
- `health_state`
- `summary`
- `detail` object
- `source_ref` (stable/idempotent report identity)
- `needs_attention` boolean
- `severity`
- optional display/department/role/action metadata for first registration

Processed files are renamed `.processed`; invalid or unreadable reports are renamed `.error`. The report inbox is watched by `edge1-ava-executive.path`, so native reports do not wait for a timer.

## Triggers

`edge1-ava-executive.path` wakes the orchestrator when Automation Center inventory changes or a direct report arrives. `edge1-ava-executive.timer` is a ten-minute reconciliation fallback, not the primary coordination mechanism.

## Read API and UI

The Ava Office read service remains loopback-only on 127.0.0.1:8116. Executive endpoints are read-only:

- `/api/ava-office/executive`
- `/api/ava-office/team`
- `/api/ava-office/assignments`
- `/api/ava-office/reports`

Nginx exposes these through the existing authenticated Edge1 session under `/edge1-ops/ava-office/api/`. The Edge1 AVA page at `/edge1-ops/status/ava/` provides Team, Assignments, Executive Inbox, Work Queue and Needs You views.

## Safety boundary

AVA Executive does not execute arbitrary shell commands, accept credentials in reports, or supersede Operations API, Security Auth, source registries, Contacts gates, evidence policy, or provider-specific controls. It is an orchestration and executive state layer over those control planes.

## Executive Dispatcher and Workflow Engine

AVA also owns a bounded workflow dispatcher. The capability contract is stored in `config/ava-executive-capabilities.json`. Workflow requests are written to `/var/lib/wwcx-ava-office-manager/workflow-inbox/` and are consumed by `edge1-ava-workflow-dispatcher.path` immediately, with `edge1-ava-workflow-dispatcher.timer` as a five-minute reconciliation fallback.

The dispatcher accepts only autonomous capabilities explicitly present in the registry. Current transports are loopback HTTP JSON actions. Non-loopback endpoints, unknown transports, unknown capabilities and capabilities above the assigned team member's AVA authority ceiling fail closed. Workflow requests cannot contain an arbitrary command, unit name or executable path.

`edge1-ava-dispatch-admin.service` is the privileged bounded service-action broker. It exposes only a compiled allow-list of existing Edge1 service actions on `127.0.0.1:8801`; callers cannot supply commands, arguments, paths, environment variables or unit names. The existing Library Sources admin broker remains responsible for Library/evidence/accounting actions on `127.0.0.1:8800`.

Workflow runs and steps are durable in the Ava Office database. Each step records its capability, responsible team member, dependencies, attempt count, state, timestamps and bounded result/error metadata. The Ava Office read API exposes `/api/ava-office/workflows`, and the Edge1 AVA Executive Office has a Workflows view.

The initial autonomous workflows are:

- Provider Evidence Processing: provider poll -> catalog refresh -> evidence search indexing -> Contacts/evidence intake and Accounting extraction.
- Local Evidence Processing: catalog refresh -> evidence indexing -> Contacts/evidence intake and Accounting extraction.
- Spamhaus Maintenance Recovery: retry the existing Spamhaus AUTO-FIX service.
- Suricata Maintenance Recovery: retry the existing Suricata AUTO-FIX service.
- Automation Health Recovery: bounded service self-heal -> Automation Watchdog re-audit.
- Released Mail Processing: Contacts extraction and document filing -> accounting intake.
- Executive Reporting Cycle: evidence/backup verification -> AVA daily/weekly briefing generation.

External provider polling submits Provider Evidence Processing only when a provider run reports new or changed items. Continuing team-attention episodes use one stable attention work item; mapped remediation is submitted once per attention episode rather than on every check-in.

## Retry and escalation policy

Registered capability failures receive a bounded retry on a later dispatcher cycle (default two attempts total). A policy/authority block stops immediately. Exhausted retries move the associated AVA work item to owner review rather than looping indefinitely.

For team-attention remediation, a successful maintenance command does not by itself close the incident. The attention item waits for a fresh healthy team report; the Executive Orchestrator closes it only after the bot's health state actually recovers.

This keeps AVA highly autonomous for routine backend coordination while preserving explicit escalation for ambiguity, persistent failure and restricted operations.
