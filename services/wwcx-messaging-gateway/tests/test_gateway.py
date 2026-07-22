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


def test_telegraph_office_page_is_available() -> None:
    response = client.get("/telegraph-office")
    assert response.status_code == 200
    assert "SPIRIT CREEK TELEGRAPH OFFICE" in response.text


def test_telegraph_dispatch_creates_verified_receipt() -> None:
    reset_store()
    response = client.post(
        "/v1/telegraph/dispatch",
        headers={"X-WWCX-Simulator-Token": "development-only"},
        json={
            "sender": "Spirit Creek Telegraph Office",
            "recipients": ["+15550100001"],
            "channel": "sms",
            "text": "Yee Haw!",
            "security_mode": "plain",
            "client_observed_at_utc": "2026-07-22T07:13:49Z",
        },
    )
    assert response.status_code == 202
    data = response.json()
    assert data["accepted"] is True
    assert data["coordinates_attached"] is False
    assert len(data["content_sha256"]) == 64
    assert store.count() == 1


def test_coordinate_attestation_requires_consent() -> None:
    response = client.post(
        "/v1/telegraph/dispatch",
        headers={"X-WWCX-Simulator-Token": "development-only"},
        json={
            "sender": "Spirit Creek Telegraph Office",
            "recipients": ["+15550100001"],
            "text": "Location test",
            "coordinates": {
                "latitude": 64.1466,
                "longitude": -21.9426,
                "accuracy_m": 25,
                "source": "browser",
                "observed_at": "2026-07-22T07:13:49Z",
                "consent": False,
            },
        },
    )
    assert response.status_code == 422


def test_encrypted_dispatch_records_fingerprints_without_keys() -> None:
    reset_store()
    response = client.post(
        "/v1/telegraph/dispatch",
        headers={"X-WWCX-Simulator-Token": "development-only"},
        json={
            "sender": "Spirit Creek Telegraph Office",
            "recipients": ["+15550100001"],
            "channel": "mms",
            "text": "-----BEGIN PGP MESSAGE-----\nabc\n-----END PGP MESSAGE-----",
            "ciphertext_armored": "-----BEGIN PGP MESSAGE-----\nabc\n-----END PGP MESSAGE-----",
            "security_mode": "encrypted_and_signed",
            "recipient_fingerprints": ["A1B2C3D4"],
            "signer_fingerprint": "9ABCDEF0",
        },
    )
    assert response.status_code == 202
    ledger = client.get(
        "/v1/telegraph/ledger",
        headers={"X-WWCX-Simulator-Token": "development-only"},
    )
    assert ledger.status_code == 200
    security = ledger.json()["events"][0]["verification"]["security"]
    assert security["mode"] == "encrypted_and_signed"
    assert security["recipient_fingerprints"] == ["A1B2C3D4"]
    assert "private_key" not in str(ledger.json()).lower()
    assert "passphrase" not in str(ledger.json()).lower()
