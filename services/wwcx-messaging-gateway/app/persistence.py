from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .models import Direction, NormalizedMessage


@dataclass(frozen=True)
class ClaimedOutboundJob:
    job_id: UUID
    message: NormalizedMessage
    attempt_count: int


class PostgresEventStore:
    """PostgreSQL-backed idempotent event, message, control, and outbound queue store."""

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
                    (message.event_id, message.provider, message.provider_event_id, "message.received", Jsonb(payload)),
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

    def enqueue_outbound(self, message: NormalizedMessage) -> bool:
        if message.direction != Direction.OUTBOUND:
            raise ValueError("outbound queue accepts outbound messages only")
        payload = message.model_dump(mode="json", by_alias=True)
        job_id = uuid4()
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
                        "message.outbound.queued",
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
                    VALUES (%s, %s, NULL, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        message.event_id,
                        message.provider,
                        message.direction.value,
                        message.channel.value,
                        message.sender,
                        Jsonb(message.recipients),
                        message.text,
                        "queued",
                        message.occurred_at,
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO outbound_jobs (id, message_id)
                    VALUES (%s, %s)
                    """,
                    (job_id, message.event_id),
                )
        return True

    def claim_outbound_job(self) -> ClaimedOutboundJob | None:
        with psycopg.connect(self.database_url, row_factory=dict_row) as connection:
            with connection.transaction():
                row = connection.execute(
                    """
                    SELECT j.id, j.attempt_count, e.payload
                    FROM outbound_jobs AS j
                    JOIN messaging_events AS e
                      ON e.id = j.message_id
                     AND e.event_type = 'message.outbound.queued'
                    WHERE j.state = 'pending'
                      AND j.available_at <= now()
                    ORDER BY j.available_at, j.created_at, j.id
                    FOR UPDATE OF j SKIP LOCKED
                    LIMIT 1
                    """
                ).fetchone()
                if row is None:
                    return None
                attempt_count = int(row["attempt_count"]) + 1
                connection.execute(
                    """
                    UPDATE outbound_jobs
                    SET state = 'processing', attempt_count = %s, locked_at = now()
                    WHERE id = %s
                    """,
                    (attempt_count, row["id"]),
                )
        return ClaimedOutboundJob(
            job_id=row["id"],
            message=NormalizedMessage.model_validate(row["payload"]),
            attempt_count=attempt_count,
        )

    def suppressed_recipients(self, recipients: list[str]) -> list[str]:
        if not recipients:
            return []
        with psycopg.connect(self.database_url) as connection:
            rows = connection.execute(
                """
                SELECT address
                FROM suppressions
                WHERE address = ANY(%s::text[])
                ORDER BY address
                """,
                (recipients,),
            ).fetchall()
        return [str(row[0]) for row in rows]

    def complete_outbound_job(self, job_id: UUID, provider_message_id: str) -> None:
        with psycopg.connect(self.database_url) as connection:
            with connection.transaction():
                row = connection.execute(
                    """
                    UPDATE outbound_jobs
                    SET state = 'sent', locked_at = NULL, last_error = NULL
                    WHERE id = %s AND state = 'processing'
                    RETURNING message_id
                    """,
                    (job_id,),
                ).fetchone()
                if row is None:
                    raise RuntimeError("outbound job is not processing")
                connection.execute(
                    """
                    UPDATE messages
                    SET status = 'sent', provider_message_id = %s
                    WHERE id = %s
                    """,
                    (provider_message_id, row[0]),
                )

    def block_outbound_job(self, job_id: UUID, reason: str, status: str = "blocked") -> None:
        with psycopg.connect(self.database_url) as connection:
            with connection.transaction():
                row = connection.execute(
                    """
                    UPDATE outbound_jobs
                    SET state = %s, locked_at = NULL, last_error = %s
                    WHERE id = %s AND state = 'processing'
                    RETURNING message_id
                    """,
                    (status, reason[:1000], job_id),
                ).fetchone()
                if row is None:
                    raise RuntimeError("outbound job is not processing")
                connection.execute(
                    """
                    UPDATE messages
                    SET status = %s
                    WHERE id = %s
                    """,
                    (status, row[0]),
                )

    def retry_outbound_job(
        self,
        job_id: UUID,
        error: str,
        *,
        delay_seconds: int = 60,
        max_attempts: int = 5,
    ) -> str:
        delay_seconds = max(1, min(int(delay_seconds), 86400))
        max_attempts = max(1, min(int(max_attempts), 100))
        with psycopg.connect(self.database_url) as connection:
            with connection.transaction():
                row = connection.execute(
                    """
                    UPDATE outbound_jobs
                    SET state = CASE WHEN attempt_count >= %s THEN 'failed' ELSE 'pending' END,
                        available_at = CASE
                            WHEN attempt_count >= %s THEN available_at
                            ELSE now() + (%s * interval '1 second')
                        END,
                        locked_at = NULL,
                        last_error = %s
                    WHERE id = %s AND state = 'processing'
                    RETURNING message_id, state
                    """,
                    (max_attempts, max_attempts, delay_seconds, error[:1000], job_id),
                ).fetchone()
                if row is None:
                    raise RuntimeError("outbound job is not processing")
                message_status = "failed" if row[1] == "failed" else "queued"
                connection.execute(
                    """
                    UPDATE messages
                    SET status = %s
                    WHERE id = %s
                    """,
                    (message_status, row[0]),
                )
        return str(row[1])

    def outbound_queue_status(self) -> dict[str, object]:
        with psycopg.connect(self.database_url) as connection:
            rows = connection.execute(
                """
                SELECT state, count(*)
                FROM outbound_jobs
                GROUP BY state
                ORDER BY state
                """
            ).fetchall()
        return {
            "durable": True,
            "counts": {str(state): int(count) for state, count in rows},
        }

    def count(self) -> int:
        with psycopg.connect(self.database_url) as connection:
            row = connection.execute("SELECT count(*) FROM messaging_events").fetchone()
            return int(row[0])

    def list_recent(self, limit: int = 50) -> list[NormalizedMessage]:
        limit = min(max(int(limit), 1), 100)
        with psycopg.connect(self.database_url, row_factory=dict_row) as connection:
            rows = connection.execute(
                """
                SELECT payload
                FROM messaging_events
                WHERE event_type = 'message.received'
                ORDER BY (payload->>'occurred_at')::timestamptz DESC, id DESC
                LIMIT %s
                """,
                (limit,),
            ).fetchall()
        return [NormalizedMessage.model_validate(row["payload"]) for row in rows]

    def get_event(self, event_id: str) -> NormalizedMessage | None:
        try:
            parsed_id = UUID(event_id)
        except ValueError:
            return None
        with psycopg.connect(self.database_url, row_factory=dict_row) as connection:
            row = connection.execute(
                """
                SELECT payload
                FROM messaging_events
                WHERE id = %s AND event_type = 'message.received'
                """,
                (parsed_id,),
            ).fetchone()
        return NormalizedMessage.model_validate(row["payload"]) if row is not None else None

    def get_control_state(self) -> dict[str, object]:
        with psycopg.connect(self.database_url, row_factory=dict_row) as connection:
            row = connection.execute(
                """
                SELECT paused, updated_at, updated_by, reason
                FROM messaging_control_state
                WHERE singleton = true
                """
            ).fetchone()
            if row is None:
                raise RuntimeError("messaging control state is not initialized")
            return {
                "paused": row["paused"],
                "last_control": {
                    "actor": row["updated_by"],
                    "reason": row["reason"],
                    "updated_at": row["updated_at"].isoformat(),
                },
            }

    def set_paused(self, paused: bool, actor: str, reason: str) -> dict[str, object]:
        action = "pause" if paused else "resume"
        with psycopg.connect(self.database_url, row_factory=dict_row) as connection:
            with connection.transaction():
                row = connection.execute(
                    """
                    UPDATE messaging_control_state
                    SET paused = %s, updated_at = now(), updated_by = %s, reason = %s
                    WHERE singleton = true
                    RETURNING paused, updated_at, updated_by, reason
                    """,
                    (paused, actor, reason),
                ).fetchone()
                connection.execute(
                    """
                    INSERT INTO messaging_control_audit (action, actor, reason)
                    VALUES (%s, %s, %s)
                    """,
                    (action, actor, reason),
                )
        if row is None:
            raise RuntimeError("messaging control state is not initialized")
        return {
            "paused": row["paused"],
            "last_control": {
                "action": action,
                "actor": row["updated_by"],
                "reason": row["reason"],
                "updated_at": row["updated_at"].isoformat(),
            },
        }

    def ping(self) -> bool:
        try:
            with psycopg.connect(self.database_url) as connection:
                return connection.execute("SELECT 1").fetchone() == (1,)
        except psycopg.Error:
            return False
