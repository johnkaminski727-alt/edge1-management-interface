from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from threading import Lock
from uuid import UUID, uuid4

import psycopg
from psycopg.rows import dict_row

from .models import NormalizedMessage


_ALLOWED_PROCESSING_STATES = {"verified", "accepted", "duplicate"}


def _body_sha256(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


class InMemoryWebhookReceiptLedger:
    """Development-only receipt ledger mirroring the durable PostgreSQL contract."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._receipts: dict[UUID, dict[str, object]] = {}

    def record_verified(self, provider: str, message: NormalizedMessage, body: bytes) -> UUID:
        receipt_id = uuid4()
        record = {
            "id": receipt_id,
            "provider": provider,
            "provider_event_id": message.provider_event_id,
            "message_event_id": message.event_id,
            "body_sha256": _body_sha256(body),
            "verification_status": "verified",
            "processing_status": "verified",
            "received_at": datetime.now(timezone.utc),
            "processed_at": None,
        }
        with self._lock:
            self._receipts[receipt_id] = record
        return receipt_id

    def mark_processed(self, receipt_id: UUID, processing_status: str) -> None:
        if processing_status not in {"accepted", "duplicate"}:
            raise ValueError("unsupported webhook processing status")
        with self._lock:
            record = self._receipts.get(receipt_id)
            if record is None:
                raise RuntimeError("webhook receipt not found")
            if record["processing_status"] != "verified":
                raise RuntimeError("webhook receipt is already processed")
            record["processing_status"] = processing_status
            record["processed_at"] = datetime.now(timezone.utc)

    def status(self, limit: int = 25) -> dict[str, object]:
        bounded_limit = min(max(int(limit), 1), 100)
        with self._lock:
            records = list(self._receipts.values())
        records.sort(key=lambda item: (item["received_at"], str(item["id"])), reverse=True)
        counts = {state: 0 for state in sorted(_ALLOWED_PROCESSING_STATES)}
        for record in records:
            counts[str(record["processing_status"])] += 1
        recent = [self._sanitize(record) for record in records[:bounded_limit]]
        return {"durable": False, "counts": counts, "recent_receipts": recent}

    @staticmethod
    def _sanitize(record: dict[str, object]) -> dict[str, object]:
        return {
            "id": str(record["id"]),
            "provider": str(record["provider"]),
            "provider_event_id": str(record["provider_event_id"]),
            "message_event_id": str(record["message_event_id"]),
            "body_sha256": str(record["body_sha256"]),
            "verification_status": str(record["verification_status"]),
            "processing_status": str(record["processing_status"]),
            "received_at": record["received_at"].isoformat(),
            "processed_at": record["processed_at"].isoformat() if record["processed_at"] else None,
        }


class PostgresWebhookReceiptLedger:
    """Durable audit ledger for verified, normalized provider webhook attempts.

    Unverified requests are intentionally not persisted here. A future public
    endpoint must not turn invalid unauthenticated traffic into an unbounded
    database-write primitive. Provider-specific verification remains responsible
    for signature authenticity and freshness/replay-window checks.
    """

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def record_verified(self, provider: str, message: NormalizedMessage, body: bytes) -> UUID:
        receipt_id = uuid4()
        with psycopg.connect(self.database_url) as connection:
            connection.execute(
                """
                INSERT INTO messaging_webhook_receipts
                    (id, provider, provider_event_id, message_event_id, body_sha256,
                     verification_status, processing_status)
                VALUES (%s, %s, %s, %s, %s, 'verified', 'verified')
                """,
                (
                    receipt_id,
                    provider,
                    message.provider_event_id,
                    message.event_id,
                    _body_sha256(body),
                ),
            )
        return receipt_id

    def mark_processed(self, receipt_id: UUID, processing_status: str) -> None:
        if processing_status not in {"accepted", "duplicate"}:
            raise ValueError("unsupported webhook processing status")
        with psycopg.connect(self.database_url) as connection:
            row = connection.execute(
                """
                UPDATE messaging_webhook_receipts
                SET processing_status = %s, processed_at = now()
                WHERE id = %s AND processing_status = 'verified'
                RETURNING id
                """,
                (processing_status, receipt_id),
            ).fetchone()
            if row is None:
                raise RuntimeError("webhook receipt not found or already processed")

    def status(self, limit: int = 25) -> dict[str, object]:
        bounded_limit = min(max(int(limit), 1), 100)
        with psycopg.connect(self.database_url, row_factory=dict_row) as connection:
            count_rows = connection.execute(
                """
                SELECT processing_status, count(*) AS count
                FROM messaging_webhook_receipts
                GROUP BY processing_status
                ORDER BY processing_status
                """
            ).fetchall()
            recent_rows = connection.execute(
                """
                SELECT id, provider, provider_event_id, message_event_id, body_sha256,
                       verification_status, processing_status, received_at, processed_at
                FROM messaging_webhook_receipts
                ORDER BY received_at DESC, id DESC
                LIMIT %s
                """,
                (bounded_limit,),
            ).fetchall()

        counts = {state: 0 for state in sorted(_ALLOWED_PROCESSING_STATES)}
        counts.update({str(row["processing_status"]): int(row["count"]) for row in count_rows})
        recent = [
            {
                "id": str(row["id"]),
                "provider": str(row["provider"]),
                "provider_event_id": str(row["provider_event_id"]),
                "message_event_id": str(row["message_event_id"]),
                "body_sha256": str(row["body_sha256"]),
                "verification_status": str(row["verification_status"]),
                "processing_status": str(row["processing_status"]),
                "received_at": row["received_at"].isoformat(),
                "processed_at": row["processed_at"].isoformat() if row["processed_at"] else None,
            }
            for row in recent_rows
        ]
        return {"durable": True, "counts": counts, "recent_receipts": recent}
