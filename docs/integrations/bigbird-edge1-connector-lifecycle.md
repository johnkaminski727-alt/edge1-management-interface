# BigBird Edge1 Connector Lifecycle

## Purpose

Provides a controlled read-only lifecycle layer between BigBird and the Edge1 Operations API.

## Security model

The connector uses the Edge1 Operations API rather than SSH, arbitrary shell access, or direct database access.

Initial enabled capabilities:

- repository status
- numbering health
- numbering validation
- interconnect validation
- telephony health
- security configuration validation

Mutation capabilities remain disabled.

The connector capability inventory is fail-closed. Every Operations API action must be explicitly classified as enabled or disabled in `config/bigbird-edge1-connector.json`. New Operations API actions are not automatically granted to the connector; an unclassified advertised action causes refresh to fail until the connector policy is deliberately reconciled.

## Persistent state boundary

Lifecycle refresh records bounded local state and audit events under `/var/lib/bigbird-edge1-connector`.

Both connector oneshot units run with `ProtectSystem=strict` and explicitly allow writes only to that state directory. The repository remains read-only to the service. This write exception is required for `restart-state.json` and `audit.jsonl`; removing it causes lifecycle refresh to fail before a successful state update can be persisted.

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
2. Verify the Operations API remains read-only.
3. Authenticate to the loopback Operations API.
4. Rediscover the API action inventory.
5. Reject missing required actions or any unclassified advertised action.
6. Write the bounded state record and audit event.
7. Schedule the next due refresh according to the connector-only policy.

## Future mutation workflow

Mutation actions require a separate approval, execution, verification, and rollback workflow.
