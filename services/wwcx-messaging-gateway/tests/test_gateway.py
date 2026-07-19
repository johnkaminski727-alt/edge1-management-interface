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


def reset_store() -> None:
    store._events.clear()
    store.set_paused(False, "test-suite", "reset state")


def test_health() -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_simulator_authentication_required() -> None:
    response = client.post("/v1/simulator/messages", json=payload())
    assert response.status_code == 401


def test_duplicate_provider_event_is_idempotent() -> None:
    reset_store()
    headers = {"X-WWCX-Simulator-Token": "development-only"}
    first = client.post("/v1/simulator/messages", json=payload(), headers=headers)
    second = client.post("/v1/simulator/messages", json=payload(), headers=headers)
    assert first.status_code == 202
    assert first.json()["accepted"] is True
    assert second.status_code == 202
    assert second.json()["duplicate"] is True


def test_management_status_requires_read_token() -> None:
    assert client.get("/v1/management/status").status_code == 401
    response = client.get(
        "/v1/management/status",
        headers={"X-WWCX-Management-Token": "development-read-only"},
    )
    assert response.status_code == 200
    assert response.json()["service"] == "wwcx-messaging-gateway"


def test_controls_are_disabled_by_default() -> None:
    response = client.post(
        "/v1/management/control",
        headers={"X-WWCX-Control-Token": "development-control-only"},
        json={"action": "pause", "actor": "bigbird", "reason": "maintenance"},
    )
    assert response.status_code == 403


def test_enabled_pause_blocks_intake(monkeypatch) -> None:
    reset_store()
    monkeypatch.setenv("WWCX_MANAGEMENT_CONTROL_ENABLED", "true")
    pause = client.post(
        "/v1/management/control",
        headers={"X-WWCX-Control-Token": "development-control-only"},
        json={"action": "pause", "actor": "bigbird", "reason": "maintenance"},
    )
    assert pause.status_code == 200
    assert pause.json()["paused"] is True

    blocked = client.post(
        "/v1/simulator/messages",
        headers={"X-WWCX-Simulator-Token": "development-only"},
        json=payload(),
    )
    assert blocked.status_code == 503

    resume = client.post(
        "/v1/management/control",
        headers={"X-WWCX-Control-Token": "development-control-only"},
        json={"action": "resume", "actor": "bigbird", "reason": "maintenance complete"},
    )
    assert resume.status_code == 200
    assert resume.json()["paused"] is False
