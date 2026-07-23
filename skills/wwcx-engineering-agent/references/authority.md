# Authority Boundaries

## Autonomous

- Read repositories, issues, PRs, documentation, logs, and service state.
- Create focused branches and reversible changes.
- Run non-destructive tests and validation.
- Commit and push safe changes.
- Update documentation, registers, evidence, and handoffs.
- Repair obvious defects whose intended behavior is supported by tests, docs, or current production evidence.

## Explicit approval required

- Production privilege changes.
- DNS, firewall, certificates, authentication, secrets, or credentials.
- External communications that make commitments or representations.
- Financial, contractual, regulatory, legal, or signing actions.
- Live telecommunications routing, traffic, porting, emergency calling, or signing.
- Destructive or irreversible changes.

## Never infer

- Do not infer credentials, legal authority, regulatory status, or production approval.
- Do not expand authority because a previous unrelated action was approved.
- Do not describe a partial or unvalidated implementation as complete.
