# BigBird integration

BigBird manages the WW.CX messaging gateway through its internal HTTP API. BigBird must not connect directly to the messaging PostgreSQL database, provider credentials, or carrier webhooks.

## Trust boundary

The messaging gateway remains the system of record for message state and operational controls. BigBird is an authenticated orchestration client.

Use separate scopes:

- `messaging.status.read`