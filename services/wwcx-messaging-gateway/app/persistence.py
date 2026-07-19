from __future__ import annotations

import psycopg
from psycopg.types.json import Jsonb

from .models import NormalizedMessage


class PostgresEventStore:
    """PostgreSQL-backed idempotent event and normalized-message store."""

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def put_if_absent(self, message: NormalizedMessage) -> bool:
        payload = message.model_dump(mode="json", by_alias=True)
        with psycopg.connect(self.database_url) as connection:
            with connection.transaction():
                inserted = connection.execute(
                    """
                    INSERT INTO messaging_events
                        (id, provider, provider_event_id, event_type, payload)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (provider, provider_event_id) DO NOTHING
                    RETURNING id
                    """,
                    (
                        message.event_id,
                        message.provider,
                        message.provider_event_id,
                        "message.received",
                        Jsonb(payload),
                    ),
                ).fetchone()
                if inserted is None:
                    return False

                connection.execute(
                    """
                    INSERT INTO messages
                        (id, provider, provider_message_id, direction, channel,
                         sender, recipients, body, status, occurred_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        message.event_id,
                        message.provider,
                        message.provider_event_id,
                        message.direction.value,
                        message.channel.value,
                        message.sender,
                        Jsonb(message.recipients),
                        message.text,
                        "received",
                        message.occurred_at,
                    ),
                )
        return True

    def count(self) -> int:
        with psycopg.connect(self.database_url) as connection:
            row = connection.execute("SELECT count(*) FROM messaging_events").fetchone()
            return int(row[0])

    def ping(self) -> bool:
        try:
            with psycopg.connect(self.database_url) as connection:
                return connection.execute("SELECT 1").fetchone() == (1,)
        except psycopg.Error:
            return False
