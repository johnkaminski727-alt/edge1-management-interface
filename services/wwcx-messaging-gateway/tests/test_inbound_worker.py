from uuid import UUID

from app.inbound_worker import run_once
from app.models import NormalizedMessage
from app.webhook_receipts import ClaimedWebhookReceipt


RECEIPT_ID = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")


def message() -> NormalizedMessage:
    return NormalizedMessage.model_validate(
        {
            "provider": "simulator",
            "provider_event_id": "recovery-unit-1",
            "direction": "inbound",
            "channel": "sms",
            "from": "+16045550120",
            "to": ["+16045550101"],
            "text": "recover me",
            "media": [],
        }
    )


class FakeReceipts:
    def __init__(self, claimed: ClaimedWebhookReceipt | None) -> None:
        self.claimed = claimed
        self.processed: tuple[UUID, str] | None = None
        self.retried: tuple[UUID, str, int, int] | None = None

    def claim_verified(self) -> ClaimedWebhookReceipt | None:
        value = self.claimed
        self.claimed = None
        return value

    def mark_processed(self, receipt_id: UUID, status: str) -> None:
        self.processed = (receipt_id, status)

    def retry_processing(
        self,
        receipt_id: UUID,
        error: str,
        *,
        delay_seconds: int,
        max_attempts: int,
    ) -> str:
        self.retried = (receipt_id, error, delay_seconds, max_attempts)
        return "verified"


class FakeStore:
    def __init__(self, *, accepted: bool = True, raises: bool = False) -> None:
        self.accepted = accepted
        self.raises = raises
        self.calls = 0

    def put_if_absent(self, inbound: NormalizedMessage) -> bool:
        self.calls += 1
        if self.raises:
            raise RuntimeError("database unavailable")
        return self.accepted


def claimed() -> ClaimedWebhookReceipt:
    return ClaimedWebhookReceipt(RECEIPT_ID, message(), 1)


def test_idle_when_no_verified_receipt() -> None:
    receipts = FakeReceipts(None)
    store = FakeStore()
    assert run_once(receipts, store) == {"status": "idle"}
    assert store.calls == 0


def test_accepts_recovered_receipt() -> None:
    receipts = FakeReceipts(claimed())
    store = FakeStore(accepted=True)
    result = run_once(receipts, store)
    assert result["status"] == "accepted"
    assert receipts.processed == (RECEIPT_ID, "accepted")
    assert receipts.retried is None


def test_marks_recovered_replay_duplicate() -> None:
    receipts = FakeReceipts(claimed())
    store = FakeStore(accepted=False)
    result = run_once(receipts, store)
    assert result["status"] == "duplicate"
    assert receipts.processed == (RECEIPT_ID, "duplicate")


def test_retries_database_processing_failure_safely() -> None:
    receipts = FakeReceipts(claimed())
    store = FakeStore(raises=True)
    result = run_once(receipts, store, retry_delay_seconds=7, max_attempts=3)
    assert result["status"] == "verified"
    assert result["reason"] == "message_persistence_error"
    assert receipts.processed is None
    assert receipts.retried is not None
    assert receipts.retried[2:] == (7, 3)
