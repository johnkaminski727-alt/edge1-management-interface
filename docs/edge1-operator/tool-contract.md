# Edge1 Operator Tool Contract

Initial tools:

- identity
- health
- preflight
- bounded execution
- file inspection
- Git inspection
- service inspection

Future phases add controlled mutation, deployment, database, and rollback operations.

All operations must return:

- execution identifier
- verified host identity
- principal
- timestamps
- exit status
- sanitized output
- evidence location

Secrets and private credentials are never returned through the tool.
