# Edge1 Autonomous Completion Charter

Date: 2026-07-17
Classification: internal
Project: Edge1 / Big Bird management, private library, handoff, restore, and related connector completion

## Authorization

The operator approved autonomous completion with these boundaries:

> I approve autonomous completion of the Edge1 / Big Bird management, private library, handoff, restore, and related connector project. You may make implementation decisions, create and modify project files, prepare install/update packages, write tests/docs/registers, organize backups, and provide exact server commands until the project is cleanly delivered. Preserve existing production behavior, keep credentials and backups out of Git, protect secrets, and ask before destructive actions, public exposure, billing changes, OAuth publishing, DNS changes, or expanding permissions.

## Mission

Deliver the Edge1 management interface and related Big Bird operational materials
as a restorable, documented, validated, and handoff-ready project.

## In Scope

- Edge1 management interface repository organization.
- Private Library Search UI and read-only API wrapper.
- Direct read-only Big Bird private library search bridge.
- AI filesystem write connector documentation and operator controls.
- Handoff documentation, registers, restore index, and validation scripts.
- Private library backup runbook and backup verification.
- GitHub and local bare remote synchronization.
- Exact server commands for install, validation, backup, and handoff.

## Out Of Scope Without Fresh Approval

- Public exposure of private services.
- DNS changes.
- Billing changes.
- OAuth app publishing.
- Expanding API permissions.
- Destructive filesystem or database operations.
- Committing credentials, secrets, private DB backups, tokens, or private keys.

## Definition Of Done

The project is complete when:

1. The repository has a clean worktree.
2. GitHub `origin` and `edge1-local` are pushed.
3. Static UI validation passes.
4. Private library server validation passes.
5. Live search returns `mode: live_direct`.
6. Handoff docs and registers are present.
7. A compressed private library backup exists and its manifest verifies.
8. Restore instructions identify every required repo, backup, and handoff file.

