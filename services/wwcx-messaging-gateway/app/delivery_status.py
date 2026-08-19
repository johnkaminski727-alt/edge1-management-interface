from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from .models import DeliveryStatusEvent


@dataclass(frozen=True)
class DeliveryApplyResult:
    accepted: bool
    applied: bool
    matched: bool


class InMemoryDeliveryStatusStore:
    """Development-only mirror of the durable delivery-status contract."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._events: dict[tuple[str, str], DeliveryStatusEvent] = {}
        self._state: dict[tuple[str, str], DeliveryStatusEvent] = {}

    def put_if_absent(self, event: DeliveryStatusEvent) -> DeliveryApplyResult:
        event_key = (event.provider, event.provider_event_id)
        state_key = (event.provider, event.provider_message_id)
        with self._lock:
            if event_key in self._events:
                return DeliveryApplyResult(False, False, False)
            self._events[event_key] = event
            current = self._state.get(state_key)
            applied = current is None or (
                event.occurred_at,
                event.provider_event_id,
            ) > (
                current.occurred_at,
                current.provider_event_id,
            )
            if applied:
                self._state[state_key] = event
            return DeliveryApplyResult(True, applied, False)

    def status(self, limit: int = 25) -> dict[str, object]:
        bounded_limit = min(max(int(limit), 1), 100)
        with self._lock:
            events = list(self._events.values())
            state = list(self._state.values())
        events.sort(key=lambda item: (item.occurred_at, item.provider_event_id), reverse=True)
        return {
            "durable": False,
            "event_count": len(events),
            "current_state_count": len(state),
            "unmatched_state_count": len(state),
            "recent_events": [
                {
                    "provider": item.provider,
                    "provider_event_id": item.provider_event_id,
                    "provider_message_id": item.provider_message_id,
                    "status": item.status.value,
                    "occurred_at": item.occurred_at.isoformat(),
                }
                for item in events[:bounded_limit]
            ],
        }


class PostgresDeliveryStatusStore:
    """Durable, idempotent and out-of-order-safe delivery-status reconciliation."""

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def put_if_absent(self, event: DeliveryStatusEvent) -> DeliveryApplyResult:
        with psycopg.connect(self.database_url, row_factory=dict_row) as connection:
            with connection.transaction():
                inserted = connection.execute(
                    """
                    INSERT INTO messaging_delivery_events
                        (id, provider, provider_event_id, provider_message_id,
                         status, raw_status, occurred_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (provider, provider_event_id) DO NOTHING
                    RETURNING id
                    """,
                    (
                        event.event_id,
                        event.provider,
                        event.provider_event_id,
                        event.provider_message_id,
                        event.status.value,
                        event.raw_status,
                        event.occurred_at,
                    ),
                ).fetchone()
                if inserted is None:
                    return DeliveryApplyResult(False, False, False)

                applied_state = connection.execute(
                    """
                    INSERT INTO messaging_delivery_state
                        (provider, provider_message_id, status, effective_at, source_event_id)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (provider, provider_message_id) DO UPDATE
                    SET status = EXCLUDED.status,
                        effective_at = EXCLUDED.effective_at,
                        source_event_id = EXCLUDED.source_event_id,
                        updated_at = now()
                    WHERE EXCLUDED.effective_at > messaging_delivery_state.effective_at
                       OR (
                           EXCLUDED.effective_at = messaging_delivery_state.effective_at
                           AND EXCLUDED.source_event_id > messaging_delivery_state.source_event_id
                       )
                    RETURNING provider_message_id
                    """,
                    (
                        event.provider,
                        event.provider_message_id,
                        event.status.value,
                        event.occurred_at,
                        event.provider_event_id,
                    ),
                ).fetchone()

                applied = applied_state is not None
                matched_message_id: UUID | None = None
                if applied:
                    matched_row = connection.execute(
                        """
                        UPDATE messages
                        SET status = %s
                        WHERE provider = %s
                          AND provider_message_id = %s
                          AND direction = 'outbound'
                        RETURNING id
                        """,
                        (event.status.value, event.provider, event.provider_message_id),
                    ).fetchone()
                    if matched_row is not None:
                        matched_message_id = matched_row["id"]
                        connection.execute(
                            """
                            UPDATE messaging_delivery_state
                            SET matched_message_id = %s, updated_at = now()
                            WHERE provider = %s AND provider_message_id = %s
                            """,
                            (matched_message_id, event.provider, event.provider_message_id),
                        )

                connection.execute(
                    """
                    UPDATE messaging_delivery_events
                    SET applied = %s, matched_message_id = %s
                    WHERE id = %s
                    """,
                    (applied, matched_message_id, event.event_id),
                )

        return DeliveryApplyResult(True, applied, matched_message_id is not None)

    def reconcile_one(self) -> dict[str, object]:
        """Apply one current unmatched state to a now-known outbound message."""
        with psycopg.connect(self.database_url, row_factory=dict_row) as connection:
            with connection.transaction():
                row = connection.execute(
                    """
                    SELECT provider, provider_message_id, status
                    FROM messaging_delivery_state
                    WHERE matched_message_id IS NULL
                    ORDER BY updated_at, provider, provider_message_id
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                    """
                ).fetchone()
                if row is None:
                    return {"status": "idle"}
                matched = connection.execute(
                    """
                    UPDATE messages
                    SET status = %s
                    WHERE provider = %s
                      AND provider_message_id = %s
                      AND direction = 'outbound'
                    RETURNING id
                    """,
                    (row["status"], row["provider"], row["provider_message_id"]),
                ).fetchone()
                if matched is None:
                    return {
                        "status": "unmatched",
                        "provider": row["provider"],
                        "provider_message_id": row["provider_message_id"],
                    }
                connection.execute(
                    """
                    UPDATE messaging_delivery_state
                    SET matched_message_id = %s, updated_at = now()
                    WHERE provider = %s AND provider_message_id = %s
                    """,
                    (matched["id"], row["provider"], row["provider_message_id"]),
                )
                connection.execute(
                    """
                    UPDATE messaging_delivery_events
                    SET matched_message_id = %s
                    WHERE provider = %s
                      AND provider_message_id = %s
                      AND applied = true
                      AND matched_message_id IS NULL
                    """,
                    (matched["id"], row["provider"], row["provider_message_id"]),
                )
                return {
                    "status": "matched",
                    "provider": row["provider"],
                    "provider_message_id": row["provider_message_id"],
                    "message_id": str(matched["id"]),
                }

    def status(self, limit: int = 25) -> dict[str, object]:
        bounded_limit = min(max(int(limit), 1), 100)
        with psycopg.connect(self.database_url, row_factory=dict_row) as connection:
            summary = connection.execute(
                """
                SELECT
                    (SELECT count(*) FROM messaging_delivery_events) AS event_count,
                    (SELECT count(*) FROM messaging_delivery_events WHERE applied = false) AS stale_event_count,
                    (SELECT count(*) FROM messaging_delivery_state) AS current_state_count,
                    (SELECT count(*) FROM messaging_delivery_state WHERE matched_message_id IS NULL) AS unmatched_state_count
                """
            ).fetchone()
            recent = connection.execute(
                """
                SELECT provider, provider_event_id, provider_message_id, status,
                       raw_status, occurred_at, received_at, applied, matched_message_id
                FROM messaging_delivery_events
                ORDER BY received_at DESC, id DESC
                LIMIT %s
                """,
                (bounded_limit,),
            ).fetchall()
        return {
            "durable": True,
            "event_count": int(summary["event_count"]),
            "stale_event_count": int(summary["stale_event_count"]),
            "current_state_count": int(summary["current_state_count"]),
            "unmatched_state_count": int(summary["unmatched_state_count"]),
            "recent_events": [
                {
                    "provider": row["provider"],
                    "provider_event_id": row["provider_event_id"],
                    "provider_message_id": row["provider_message_id"],
                    "status": row["status"],
                    "raw_status": row["raw_status"],
                    "occurred_at": row["occurred_at"].isoformat(),
                    "received_at": row["received_at"].isoformat(),
                    "applied": bool(row["applied"]),
                    "matched": row["matched_message_id"] is not None,
                }
                for row in recent
            ],
        }
