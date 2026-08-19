from __future__ import annotations

from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from .webhook_receipts import InMemoryWebhookReceiptLedger, PostgresWebhookReceiptLedger


def duplicate_body_matches_previous(
    ledger: InMemoryWebhookReceiptLedger | PostgresWebhookReceiptLedger,
    receipt_id: UUID,
) -> bool | None:
    """Compare this verified receipt with the prior processed attempt for its provider event ID.

    Returns True for the same raw body, False for a changed body under the same
    provider event ID, and None when no prior webhook receipt exists (for example,
    a legacy event inserted before the durable receipt ledger existed).
    """
    if isinstance(ledger, PostgresWebhookReceiptLedger):
        with psycopg.connect(ledger.database_url, row_factory=dict_row) as connection:
            current = connection.execute(
                """
                SELECT provider, provider_event_id, body_sha256, received_at
                FROM messaging_webhook_receipts
                WHERE id = %s
                """,
                (receipt_id,),
            ).fetchone()
            if current is None:
                raise RuntimeError("webhook receipt not found")
            previous = connection.execute(
                """
                SELECT body_sha256
                FROM messaging_webhook_receipts
                WHERE provider = %s
                  AND provider_event_id = %s
                  AND id <> %s
                  AND processing_status IN ('accepted', 'duplicate', 'conflict')
                ORDER BY received_at, id
                LIMIT 1
                """,
                (current["provider"], current["provider_event_id"], receipt_id),
            ).fetchone()
            if previous is None:
                return None
            return str(previous["body_sha256"]) == str(current["body_sha256"])

    with ledger._lock:  # development-only mirror of the durable comparison
        current = ledger._receipts.get(receipt_id)
        if current is None:
            raise RuntimeError("webhook receipt not found")
        previous = [
            record
            for other_id, record in ledger._receipts.items()
            if other_id != receipt_id
            and record["provider"] == current["provider"]
            and record["provider_event_id"] == current["provider_event_id"]
            and record["processing_status"] in {"accepted", "duplicate", "conflict"}
        ]
        if not previous:
            return None
        previous.sort(key=lambda record: (record["received_at"], str(record["id"])))
        return str(previous[0]["body_sha256"]) == str(current["body_sha256"])
