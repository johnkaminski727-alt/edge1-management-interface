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
