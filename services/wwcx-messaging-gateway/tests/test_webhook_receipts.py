import json

from fastapi.testclient import TestClient

from app.main import app, webhook_receipts
from app.models import NormalizedMessage
from app.webhook_receipts import InMemoryWebhookReceiptLedger

client = TestClient(app)


def _payload(provider_event_id: str) -> dict[str, object]:
    return {
        "provider": "simulator",
        "provider_event_id": provider_event_id,
        "direction": "inbound",
        "channel": "sms",
        "from": "+16045550101",
        "to": ["+16045550102"],
        "text": "receipt audit",
        "media": [],
    }


def test_in_memory_receipt_ledger_records_digest_not_body() -> None:
    ledger = InMemoryWebhookReceiptLedger()
    body = json.dumps(_payload("receipt-unit-1")).encode()
    message = NormalizedMessage.model_validate_json(body)
    receipt_id = ledger.record_verified("simulator", message, body)
    ledger.mark_processed(receipt_id, "accepted")

    status = ledger.status()
    assert status["counts"]["accepted"] == 1
    receipt = status["recent_receipts"][0]
    assert receipt["provider"] == "simulator"
    assert receipt["provider_event_id"] == "receipt-unit-1"
    assert len(receipt["body_sha256"]) == 64
    assert "receipt audit" not in json.dumps(receipt)


def test_provider_webhook_records_accepted_and_duplicate_receipts() -> None:
    provider_event_id = "receipt-endpoint-unique-001"
    body = _payload(provider_event_id)
    headers = {"X-WWCX-Signature": "development-only"}

    first = client.post("/v1/webhooks/simulator", json=body, headers=headers)
    second = client.post("/v1/webhooks/simulator", json=body, headers=headers)

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["accepted"] is True
    assert second.json()["duplicate"] is True
    assert first.json()["receipt_id"] != second.json()["receipt_id"]

    response = client.get(
        "/v1/management/webhooks/receipts?limit=100",
        headers={"X-WWCX-Management-Token": "development-read-only"},
    )
    assert response.status_code == 200
    data = response.json()
    matching = [
        receipt
        for receipt in data["recent_receipts"]
        if receipt["provider_event_id"] == provider_event_id
    ]
    assert {receipt["processing_status"] for receipt in matching} == {"accepted", "duplicate"}
    assert data["raw_body_retained"] is False
    assert data["unverified_requests_persisted"] is False


def test_unverified_webhook_does_not_create_receipt() -> None:
    before = webhook_receipts.status(100)["counts"].copy()
    response = client.post("/v1/webhooks/simulator", json=_payload("receipt-unverified-001"))
    after = webhook_receipts.status(100)["counts"].copy()
    assert response.status_code == 401
    assert after == before
