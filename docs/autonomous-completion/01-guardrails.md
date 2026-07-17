# Autonomous Completion Guardrails

Date: 2026-07-17
Classification: internal

## Allowed Without Further Approval

- Create and modify project files inside `/opt/edge1-management-interface`.
- Prepare update packages and validation scripts.
- Add or update documentation, registers, checklists, and runbooks.
- Run read-only inspections and validation checks.
- Create private backups outside git using approved backup scripts.
- Commit and push non-secret project files to configured remotes.
- Preserve or improve localhost-only service wrappers.

## Must Ask First

- Destructive actions, including deletion of project history, backups, or production data.
- Public exposure of services or opening firewall routes.
- DNS changes.
- Billing changes.
- OAuth app publishing.
- Expanding permissions beyond approved scopes.
- Committing or moving secrets, credentials, database backups, tokens, or private keys.
- Replacing production auth or security boundaries.

## Secret Handling

- Do not commit `.env` files with secrets.
- Do not commit private SQLite library backups.
- Do not paste tokens, private keys, OAuth client secrets, or password hashes into docs.
- Treat private library backup archives as internal operational data.

## Runtime Bias

Prefer:

- Localhost-bound services.
- Read-only integrations.
- Reversible updates.
- Git-tracked docs and scripts.
- Backups before stateful changes.
- Operator-readable commands and validation output.

