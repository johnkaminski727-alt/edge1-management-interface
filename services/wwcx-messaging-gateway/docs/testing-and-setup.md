# Testing and setup

## Safety boundary

This procedure starts only localhost-bound test services. It does not configure a carrier, expose a webhook, assign a DID, alter FreePBX, or change Asterisk routing.

## Requirements

- Docker Engine with Compose v2
- `curl`
- TCP ports `55432` and `58080` available on localhost

## Start the staging stack

```sh
cd services/wwcx-messaging-gateway
docker compose -f compose.test.yaml up -d --build --wait
```

The stack initializes a disposable PostgreSQL database from `migrations/` and starts the gateway on `127.0.0.1:58080`.

## Run validation

```sh
sh scripts/smoke-test.sh
```

The smoke test checks health, readiness, authenticated inbound delivery, duplicate-event rejection, and the final event count.

Run the Python suite separately when developing outside the container:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
pytest -q
python -m compileall app tests
```

## Inspect

```sh
docker compose -f compose.test.yaml ps
docker compose -f compose.test.yaml logs --no-color gateway
docker compose -f compose.test.yaml exec postgres psql -U wwcx -d wwcx_messaging -c '\\dt'
```

Expected PostgreSQL tables include `messages`, `message_media`, `suppression_entries`, `webhook_receipts`, and `outbound_jobs`.

## Stop and remove test data

```sh
docker compose -f compose.test.yaml down -v
```

## Production hold points

Do not proceed to public testing until all of the following are approved and implemented:

1. Current carrier webhook signature verification.
2. Secret management outside repository and Compose files.
3. TLS reverse proxy and restricted ingress.
4. Durable runtime repositories wired to PostgreSQL.
5. Suppression enforcement on outbound submission.
6. MMS quarantine, size limits, type validation, and scanning.
7. Rate, spend, and destination controls.
8. A dedicated non-production DID and documented rollback.
