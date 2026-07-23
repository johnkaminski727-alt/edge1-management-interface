# BigBird Edge1 Connector Lifecycle

## Purpose

Provides a controlled read-only lifecycle layer between BigBird and the Edge1 Operations API.

## Security model

The connector uses the Edge1 Operations API rather than SSH, arbitrary shell access, or direct database access.

Initial capabilities:

- repository status
- numbering health
- numbering validation
- interconnect validation
- telephony health

Mutation capabilities remain disabled.

## Restart policy

The connector uses a persistent maintenance schedule:

- initial restart interval: 6 hours
- increment: 10 minutes after each successful restart
- maximum interval: 12 hours
- restart scope: connector only

The connector does not restart:

- Edge1 host
- Asterisk
- numbering services
- databases
- public services

## Maintenance cycle

1. Check connector health.
2. Verify no active operation is running.
3. Write audit event.
4. Restart connector.
5. Verify authentication.
6. Rediscover capabilities.
7. Record completion.

## Future mutation workflow

Mutation actions require a separate approval, execution, verification, and rollback workflow.
