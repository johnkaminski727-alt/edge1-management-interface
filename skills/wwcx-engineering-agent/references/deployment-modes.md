# Deployment Modes

Select one mode before acting. Use the least powerful mode that can complete the current step.

## Inspect mode

Use Inspect mode for read-only work:

- inspect repositories, branches, commits, issues, PRs, CI, documentation, logs, listeners, and service state;
- compare expected and observed behavior;
- collect evidence and produce a diagnosis;
- prepare proposed changes without publishing them.

Inspect mode does not authorize file edits, commits, pushes, service changes, or deployment actions.

## Develop mode

Use Develop mode when repository modification is authorized:

- create or edit source, tests, configuration, documentation, and project-state files;
- run non-destructive local or CI validation;
- create focused branches and commits;
- push branches and open or update pull requests;
- prepare deployment artifacts and exact rollout instructions.

Develop mode does not authorize changing a live environment. Do not restart services, install packages, run production migrations, alter runtime configuration, or change live traffic in this mode.

## Deploy mode

Use Deploy mode only when both access and project-scoped authorization cover the named environment and service.

Deploy mode may include:

- installing approved artifacts;
- applying approved runtime configuration;
- reloading or restarting the named service;
- running approved migrations;
- verifying listeners, health endpoints, fresh logs, and service state;
- executing rollback when validation fails.

Deploy mode does not imply authority for DNS, firewall, certificate, authentication, credential, financial, legal, regulatory, telecommunications-routing, destructive, or other separately protected actions.

## Mode escalation

Escalate from Inspect to Develop or from Develop to Deploy only when:

1. the current objective requires it;
2. the necessary connector or host capability exists;
3. applicable authority explicitly covers the action;
4. the repository and environment state have been freshly verified.

When escalation is unavailable, complete every lower-mode task and report only the remaining blocked action.

## Service restart rule

Treat restart, reload, daemon-reload, enablement, package installation, and production migration as Deploy-mode actions. Never perform them merely because a validation checklist mentions them.

## Environment separation

Keep development, staging, and production evidence separate. Never use a successful development or staging check as proof that production is healthy. Verify each environment independently and label evidence with the environment, service, branch or artifact version, and time observed.
