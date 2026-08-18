from fastapi.testclient import TestClient

from app.main import app, store

client = TestClient(app)
READ_HEADERS = {"X-WWCX-Management-Token": "development-read-only"}
SIM_HEADERS = {"X-WWCX-Simulator-Token": "development-only"}


def reset_store() -> None:
    store._events.clear()
    store.set_paused(False, "test-suite", "reset state")


def message_payload() -> dict[str, object]:
    return {
        "provider": "simulator",
        "provider_event_id": "ai-read-001",
        "direction": "inbound",
        "channel": "mms",
        "from": "+16045550101",
        "to": ["+16045550102"],
        "text": "A" * 1200,
        "media": [{"url": "https://provider.invalid/private/object/123", "content_type": "image/jpeg", "sha256": "a" * 64}],
    }


def test_recent_read_requires_management_read_token() -> None:
    assert client.get("/v1/management/messages/recent").status_code == 401


def test_recent_read_is_bounded_sanitized_and_non_mutating() -> None:
    reset_store()
    accepted = client.post("/v1/simulator/messages", headers=SIM_HEADERS, json=message_payload())
    assert accepted.status_code == 202
    response = client.get("/v1/management/messages/recent?limit=500", headers=READ_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["contract"] == "wwcx.messages-conversation-read.v1"
    assert data["limit"] == 100
    assert data["content_is_untrusted"] is True
    assert data["mutation_authorized"] is False
    event = data["events"][0]
    assert len(event["text_summary"]) == 1000
    assert event["text_truncated"] is True
    assert event["media"] == [{"content_type": "image/jpeg", "sha256": "a" * 64}]
    assert "url" not in str(event).lower()
    assert event["mutation_authorized"] is False


def test_single_event_read_uses_event_id() -> None:
    reset_store()
    accepted = client.post("/v1/simulator/messages", headers=SIM_HEADERS, json=message_payload())
    event_id = accepted.json()["event_id"]
    response = client.get(f"/v1/management/messages/{event_id}", headers=READ_HEADERS)
    assert response.status_code == 200
    assert response.json()["event"]["event_id"] == event_id
    assert response.json()["mutation_authorized"] is False


def test_status_advertises_read_capabilities_not_send() -> None:
    data = client.get("/v1/management/status", headers=READ_HEADERS).json()
    assert "messages.status.read" in data["capabilities"]
    assert "messages.conversation.read" in data["capabilities"]
    assert "messages.compliance.read" in data["capabilities"]
    assert data["mutation_authorized"] is False
    assert "messages.send" not in data["capabilities"]
