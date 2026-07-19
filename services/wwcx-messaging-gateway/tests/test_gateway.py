from fastapi.testclient import TestClient

from app.main import app, store

client = TestClient(app)


def payload() -> dict[str, object]:
    return {
        "provider": "simulator",
        "provider_event_id": "evt-001",
        "direction": "inbound",
        "channel": "sms",
        "from": "+16045550101",
        "to": ["+16045550102"],
        "text": "Hello from the simulator",
        "media": [],
    }


def test_health() -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_simulator_authentication_required() -> None:
    response = client.post("/v1/simulator/messages", json=payload())
    assert response.status_code == 401


def test_duplicate_provider_event_is_idempotent() -> None:
    store._events.clear()
    headers = {"X-WWCX-Simulator-Token": "development-only"}
    first = client.post("/v1/simulator/messages", json=payload(), headers=headers)
    second = client.post("/v1/simulator/messages", json=payload(), headers=headers)
    assert first.status_code == 202
    assert first.json()["accepted"] is True
    assert second.status_code == 202
    assert second.json()["duplicate"] is True
