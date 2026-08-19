from __future__ import annotations

from threading import Lock

import psycopg
from psycopg.rows import dict_row


_ALLOWED_OUTCOMES = {
    "unknown_provider",
    "verification_failed",
    "invalid_payload",
    "paused",
    "accepted",
    "duplicate",
    "payload_conflict",
}


class InMemoryWebhookBoundaryCounters:
    def __init__(self) -> None:
        self._lock = Lock()
        self._counts: dict[tuple[str, str], int] = {}

    def record(self, provider_bucket: str, outcome: str) -> None:
        if outcome not in _ALLOWED_OUTCOMES:
            raise ValueError("unsupported webhook audit outcome")
        key = (provider_bucket[:128], outcome)
        with self._lock:
            self._counts[key] = self._counts.get(key, 0) + 1

    def status(self) -> dict[str, object]:
        with self._lock:
            rows = sorted(self._counts.items())
        return {
            "durable": False,
            "counters": [
                {"provider_bucket": key[0], "outcome": key[1], "event_count": count}
                for key, count in rows
            ],
        }


class PostgresWebhookBoundaryCounters:
    """Bounded durable counters, not one row per rejected unauthenticated request.

    Unknown provider path values are collapsed by the caller to `__unknown__`, and
    known-provider outcomes create at most one row per provider/outcome pair. This
    preserves durable probing/replay visibility without creating an attacker-
    controlled append-only database-write surface.
    """

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def record(self, provider_bucket: str, outcome: str) -> None:
        if outcome not in _ALLOWED_OUTCOMES:
            raise ValueError("unsupported webhook audit outcome")
        with psycopg.connect(self.database_url) as connection:
            connection.execute(
                """
                INSERT INTO messaging_webhook_boundary_counters
                    (provider_bucket, outcome, event_count)
                VALUES (%s, %s, 1)
                ON CONFLICT (provider_bucket, outcome) DO UPDATE
                SET event_count = messaging_webhook_boundary_counters.event_count + 1,
                    last_seen_at = now()
                """,
                (provider_bucket[:128], outcome),
            )

    def status(self) -> dict[str, object]:
        with psycopg.connect(self.database_url, row_factory=dict_row) as connection:
            rows = connection.execute(
                """
                SELECT provider_bucket, outcome, event_count, first_seen_at, last_seen_at
                FROM messaging_webhook_boundary_counters
                ORDER BY provider_bucket, outcome
                """
            ).fetchall()
        return {
            "durable": True,
            "counters": [
                {
                    "provider_bucket": row["provider_bucket"],
                    "outcome": row["outcome"],
                    "event_count": int(row["event_count"]),
                    "first_seen_at": row["first_seen_at"].isoformat(),
                    "last_seen_at": row["last_seen_at"].isoformat(),
                }
                for row in rows
            ],
        }
