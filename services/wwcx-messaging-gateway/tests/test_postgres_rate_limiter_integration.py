from __future__ import annotations

import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from uuid import UUID, uuid4

import psycopg
import pytest

from app.models import Channel, Direction, NormalizedMessage
from app.outbound_policy import PostgresSendRateLimiter


DATABASE_URL = os.getenv("DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="requires the integration Postgres DATABASE_URL",
)


def _message(*, provider: str, sender: str, event_id: UUID) -> NormalizedMessage:
    return NormalizedMessage.model_validate(
        {
            "event_id": event_id,
            "provider": provider,
            "provider_event_id": f"rate-limit-{event_id}",
            "direction": Direction.OUTBOUND,
            "channel": Channel.SMS,
            "from": sender,
            "to": ["+16045550102"],
            "text": "rate limiter integration test",
        }
    )


def _insert_job(connection: psycopg.Connection, message: NormalizedMessage, job_id: UUID) -> None:
    connection.execute(
        """
        INSERT INTO messages
            (id, provider, provider_message_id, direction, channel, sender,
             recipients, body, status, occurred_at)
        VALUES (%s, %s, NULL, %s, %s, %s, %s::jsonb, %s, %s, %s)
        """,
        (
            message.event_id,
            message.provider,
            message.direction.value,
            message.channel.value,
            message.sender,
            json.dumps(message.recipients),
            message.text,
            "queued",
            datetime.now(timezone.utc),
        ),
    )
    connection.execute(
        "INSERT INTO outbound_jobs (id, message_id) VALUES (%s, %s)",
        (job_id, message.event_id),
    )


def _delete_messages(message_ids: list[UUID]) -> None:
    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL) as connection:
        connection.execute("DELETE FROM messages WHERE id = ANY(%s)", (message_ids,))


def _reservation_count(provider: str, sender: str) -> int:
    assert DATABASE_URL is not None
    with psycopg.connect(DATABASE_URL) as connection:
        row = connection.execute(
            """
            SELECT count(*)
            FROM messaging_outbound_send_reservations
            WHERE provider = %s AND sender = %s
            """,
            (provider, sender),
        ).fetchone()
    assert row is not None
    return int(row[0])


def test_concurrent_reservations_allow_exactly_one_at_limit_one() -> None:
    assert DATABASE_URL is not None
    provider = f"rate-limit-concurrency-{uuid4().hex}"
    sender = f"sender-{uuid4().hex}"
    message_ids = [uuid4(), uuid4()]
    job_ids = [uuid4(), uuid4()]
    messages = [
        _message(provider=provider, sender=sender, event_id=message_ids[0]),
        _message(provider=provider, sender=sender, event_id=message_ids[1]),
    ]

    try:
        with psycopg.connect(DATABASE_URL) as connection:
            _insert_job(connection, messages[0], job_ids[0])
            _insert_job(connection, messages[1], job_ids[1])

        limiter = PostgresSendRateLimiter(DATABASE_URL)
        barrier = threading.Barrier(2)

        def reserve(index: int) -> str | None:
            barrier.wait(timeout=10)
            return limiter.reserve(
                job_ids[index],
                messages[index],
                hourly_limit=1,
                daily_limit=1,
            )

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(reserve, index) for index in range(2)]
            results = [future.result(timeout=20) for future in futures]

        assert results.count(None) == 1
        assert results.count("hourly_message_limit_exceeded") == 1
        assert _reservation_count(provider, sender) == 1
    finally:
        _delete_messages(message_ids)


def test_repeating_same_job_is_idempotent_and_does_not_double_count() -> None:
    assert DATABASE_URL is not None
    provider = f"rate-limit-idempotency-{uuid4().hex}"
    sender = f"sender-{uuid4().hex}"
    message_id = uuid4()
    job_id = uuid4()
    message = _message(provider=provider, sender=sender, event_id=message_id)

    try:
        with psycopg.connect(DATABASE_URL) as connection:
            _insert_job(connection, message, job_id)

        limiter = PostgresSendRateLimiter(DATABASE_URL)
        first = limiter.reserve(job_id, message, hourly_limit=1, daily_limit=1)
        second = limiter.reserve(job_id, message, hourly_limit=1, daily_limit=1)

        assert first is None
        assert second is None
        assert _reservation_count(provider, sender) == 1
    finally:
        _delete_messages([message_id])
