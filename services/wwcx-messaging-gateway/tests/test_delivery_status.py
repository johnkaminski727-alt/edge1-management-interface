from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.delivery_status import InMemoryDeliveryStatusStore
from app.main import app
from app.models import DeliveryStatusEvent

client = TestClient(app)


def event(provider_event_id: str, *, status: str = "delivered", occurred_at: str = "2026-08-19T00:30:00Z") -> dict[str, object]:
    return {
        "provider": "simulator",
        "provider_event_id": provider_event_id,
        "provider_message_id": "sim-delivery-unit-1",
        "status": status,
        "occurred_at": occurred_at,
        "raw_status": f"simulator-{status}",
    }


def test_in_memory_delivery_state_is_idempotent_and_out_of_order_safe() -> None:
    store = InMemoryDeliveryStatusStore()
    newer = DeliveryStatusEvent.model_validate(event("delivery-state-newer"))
    older = DeliveryStatusEvent.model_validate(
        event("delivery-state-older", status="failed", occurred_at="2026-08-19T00:29:00Z")
    )

    first = store.put_if_absent(newer)
    replay = store.put_if_absent(newer)
    stale = store.put_if_absent(older)

    assert first.accepted is True and first.applied is True
    assert replay.accepted is False
    assert stale.accepted is True and stale.applied is False
    status = store.status(100)
    assert status["event_count"] == 2
    assert status["current_state_count"] == 1


def test_delivery_webhook_accepts_duplicate_and_stale_events() -> None:
    headers = {"X-WWCX-Signature": "development-only"}
    provider_message_id = "sim-delivery-endpoint-unique-001"
    base = event("delivery-endpoint-newer")
    base["provider_message_id"] = provider_message_id

    first = client.post("/v1/webhooks/simulator/delivery", json=base, headers=headers)
    replay = client.post("/v1/webhooks/simulator/delivery", json=base, headers=headers)
    stale_payload = event("delivery-endpoint-stale", status="failed", occurred_at="2026-08-19T00:29:00Z")
    stale_payload["provider_message_id"] = provider_message_id
    stale = client.post("/v1/webhooks/simulator/delivery", json=stale_payload, headers=headers)

    assert first.status_code == 202
    assert first.json()["accepted"] is True
    assert first.json()["applied"] is True
    assert replay.status_code == 202
    assert replay.json()["duplicate"] is True
    assert stale.status_code == 202
    assert stale.json()["accepted"] is True
    assert stale.json()["applied"] is False


def test_delivery_webhook_rejects_wrong_provider_identity() -> None:
    payload = event("delivery-provider-mismatch")
    payload["provider"] = "telnyx"
    response = client.post(
        "/v1/webhooks/simulator/delivery",
        json=payload,
        headers={"X-WWCX-Signature": "development-only"},
    )
    assert response.status_code == 400


def test_delivery_webhook_requires_verification() -> None:
    response = client.post("/v1/webhooks/simulator/delivery", json=event("delivery-no-signature"))
    assert response.status_code == 401


def test_delivery_management_surface_is_read_only_and_protected() -> None:
    unauthorized = client.get("/v1/management/delivery/status")
    assert unauthorized.status_code == 401

    response = client.get(
        "/v1/management/delivery/status?limit=100",
        headers={"X-WWCX-Management-Token": "development-read-only"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["contract"] == "wwcx.messages-delivery-status-read.v1"
    assert data["mutation_authorized"] is False
    assert "recent_events" in data


def test_delivery_event_timestamp_is_timezone_aware() -> None:
    item = DeliveryStatusEvent.model_validate(event("delivery-timezone-test"))
    assert item.occurred_at.tzinfo is not None
    assert item.occurred_at.astimezone(timezone.utc) == datetime(2026, 8, 19, 0, 30, tzinfo=timezone.utc)
