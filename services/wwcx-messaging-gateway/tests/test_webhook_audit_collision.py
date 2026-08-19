from fastapi.testclient import TestClient

from app.main import app, webhook_audit

client = TestClient(app)


def payload(provider_event_id: str, text: str) -> dict[str, object]:
    return {
        "event_id": "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee",
        "provider": "simulator",
        "provider_event_id": provider_event_id,
        "direction": "inbound",
        "channel": "sms",
        "from": "+16045550131",
        "to": ["+16045550101"],
        "text": text,
        "media": [],
        "occurred_at": "2026-08-19T00:40:00Z",
    }


def counter(provider_bucket: str, outcome: str) -> int:
    for item in webhook_audit.status()["counters"]:
        if item["provider_bucket"] == provider_bucket and item["outcome"] == outcome:
            return int(item["event_count"])
    return 0


def test_same_provider_event_id_with_changed_body_is_conflict() -> None:
    headers = {"X-WWCX-Signature": "development-only"}
    provider_event_id = "collision-unique-001"
    first = client.post(
        "/v1/webhooks/simulator",
        json=payload(provider_event_id, "original body"),
        headers=headers,
    )
    changed = client.post(
        "/v1/webhooks/simulator",
        json=payload(provider_event_id, "changed body"),
        headers=headers,
    )
    assert first.status_code == 202
    assert changed.status_code == 409
    assert "does not match" in changed.json()["detail"]


def test_verification_failures_increment_bounded_known_provider_counter() -> None:
    before = counter("simulator", "verification_failed")
    response = client.post(
        "/v1/webhooks/simulator",
        json=payload("audit-verification-001", "bad signature"),
        headers={"X-WWCX-Signature": "wrong"},
    )
    assert response.status_code == 401
    assert counter("simulator", "verification_failed") == before + 1


def test_unknown_provider_names_collapse_into_one_bounded_bucket() -> None:
    before = counter("__unknown__", "unknown_provider")
    first = client.post("/v1/webhooks/attacker-value-one", json={})
    second = client.post("/v1/webhooks/attacker-value-two", json={})
    assert first.status_code == 404
    assert second.status_code == 404
    assert counter("__unknown__", "unknown_provider") == before + 2
    buckets = {
        item["provider_bucket"]
        for item in webhook_audit.status()["counters"]
        if item["outcome"] == "unknown_provider"
    }
    assert buckets == {"__unknown__"}


def test_webhook_audit_management_surface_is_protected_and_read_only() -> None:
    unauthorized = client.get("/v1/management/webhooks/audit")
    assert unauthorized.status_code == 401
    response = client.get(
        "/v1/management/webhooks/audit",
        headers={"X-WWCX-Management-Token": "development-read-only"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["contract"] == "wwcx.messages-webhook-audit-read.v1"
    assert data["storage_model"] == "bounded_aggregate_counters"
    assert data["raw_request_data_retained"] is False
    assert data["mutation_authorized"] is False
