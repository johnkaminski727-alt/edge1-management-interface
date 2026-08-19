from __future__ import annotations

import argparse
import json
import os

from .persistence import PostgresEventStore
from .webhook_receipts import PostgresWebhookReceiptLedger


def run_once(
    receipts: PostgresWebhookReceiptLedger,
    store: PostgresEventStore,
    *,
    retry_delay_seconds: int = 30,
    max_attempts: int = 5,
) -> dict[str, object]:
    receipt = receipts.claim_verified()
    if receipt is None:
        return {"status": "idle"}

    try:
        accepted = store.put_if_absent(receipt.message)
    except Exception as exc:
        state = receipts.retry_processing(
            receipt.receipt_id,
            f"message persistence raised {type(exc).__name__}",
            delay_seconds=retry_delay_seconds,
            max_attempts=max_attempts,
        )
        return {
            "status": state,
            "reason": "message_persistence_error",
            "receipt_id": str(receipt.receipt_id),
        }

    processing_status = "accepted" if accepted else "duplicate"
    receipts.mark_processed(receipt.receipt_id, processing_status)
    return {
        "status": processing_status,
        "receipt_id": str(receipt.receipt_id),
        "event_id": str(receipt.message.event_id),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Process one durable WW.CX inbound webhook receipt")
    parser.add_argument("--once", action="store_true", help="required safety gate; process at most one receipt")
    args = parser.parse_args()

    if not args.once:
        parser.error("--once is required; continuous inbound recovery is not enabled")

    if os.getenv("WWCX_INBOUND_WORKER_ENABLED", "false").lower() != "true":
        print(json.dumps({"status": "disabled"}))
        return 2

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print(json.dumps({"status": "error", "reason": "DATABASE_URL is required"}))
        return 2

    result = run_once(
        PostgresWebhookReceiptLedger(database_url),
        PostgresEventStore(database_url),
        retry_delay_seconds=int(os.getenv("WWCX_INBOUND_RETRY_DELAY_SECONDS", "30")),
        max_attempts=int(os.getenv("WWCX_INBOUND_MAX_ATTEMPTS", "5")),
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
