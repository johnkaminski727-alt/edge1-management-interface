"""Tests for the provider-neutral webhook dispatch endpoint and SimulatorProvider.

This exercises MessagingProvider.verify_webhook/normalize_webhook end-to-end
for the first time -- previously the ABC existed but nothing in the app used
it (the /v1/simulator/messages endpoint bypassed it entirely).

Also proves the dispatch boundary is generic (ProviderWebhookRequest: raw
body + headers) rather than assuming WWCX-specific header names or a dict
payload -- SimulatorProvider is just the reference implementation, not the
shape every provider must match.
"""
import json

import pytest
from fastapi.testclient import TestClient

from app.main import app, store
from app.models import NormalizedMessage
from app.providers import ProviderWebhookRequest, SimulatorProvider

client = TestClient(app)


def payload() -> dict[str, object]:
    return {
        "provider": "simulator",
        "provider_event_id": "webhook-evt-001",
        "direction": "inbound",
        "channel": "sms",
        "from": "+16045550101",
        "to": ["+16045550102"],
        "text": "Hello via provider webhook path",
        "media": [],
    }


def reset_store() -> None:
    store._events.clear()
    store.set_paused(False, "test-suite", "reset state")


def test_unknown_provider_returns_404() -> None:
    response = client.post("/v1/webhooks/does-not-exist", json=payload())
    assert response.status_code == 404


def test_missing_signature_is_rejected() -> None:
    response = client.post("/v1/webhooks/simulator", json=payload())
    assert response.status_code == 401


def test_wrong_signature_is_rejected() -> None:
    response = client.post(
        "/v1/webhooks/simulator",
        json=payload(),
        headers={"X-WWCX-Signature": "not-the-token"},
    )
    assert response.status_code == 401


def test_valid_simulator_webhook_is_accepted_and_idempotent() -> None:
    reset_store()
    headers = {"X-WWCX-Signature": "development-only"}
    first = client.post("/v1/webhooks/simulator", json=payload(), headers=headers)
    second = client.post("/v1/webhooks/simulator", json=payload(), headers=headers)
    assert first.status_code == 202
    assert first.json()["accepted"] is True
    assert first.json()["provider"] == "simulator"
    assert second.status_code == 202
    assert second.json()["duplicate"] is True
    assert store.count() == 1


def test_paused_intake_blocks_webhook() -> None:
    reset_store()
    store.set_paused(True, "test-suite", "pause for test")
    response = client.post(
        "/v1/webhooks/simulator",
        json=payload(),
        headers={"X-WWCX-Signature": "development-only"},
    )
    assert response.status_code == 503
    store.set_paused(False, "test-suite", "resume")


def test_invalid_json_body_returns_400() -> None:
    response = client.post(
        "/v1/webhooks/simulator",
        content=b"not json",
        headers={
            "X-WWCX-Signature": "development-only",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 400


def test_valid_json_but_schema_mismatch_returns_400() -> None:
    response = client.post(
        "/v1/webhooks/simulator",
        content=json.dumps({"not": "a normalized message"}).encode(),
        headers={
            "X-WWCX-Signature": "development-only",
            "Content-Type": "application/json",
        },
    )
    assert response.status_code == 400


def test_webhook_rejects_payload_for_different_provider() -> None:
    body = payload()
    body["provider"] = "telnyx"
    response = client.post(
        "/v1/webhooks/simulator",
        json=body,
        headers={"X-WWCX-Signature": "development-only"},
    )
    assert response.status_code == 400


def test_webhook_rejects_outbound_direction() -> None:
    body = payload()
    body["direction"] = "outbound"
    response = client.post(
        "/v1/webhooks/simulator",
        json=body,
        headers={"X-WWCX-Signature": "development-only"},
    )
    assert response.status_code == 400


def test_management_status_advertises_providers() -> None:
    response = client.get(
        "/v1/management/status",
        headers={"X-WWCX-Management-Token": "development-read-only"},
    )
    assert response.status_code == 200
    assert response.json()["providers"] == ["simulator"]


def test_simulator_provider_send_returns_accepted_result() -> None:
    provider = SimulatorProvider(lambda: "development-only")
    body = payload()
    body["direction"] = "outbound"
    message = NormalizedMessage.model_validate(body)
    result = provider.send(message)
    assert result.accepted is True
    assert result.provider_message_id == f"sim-{message.event_id}"


def test_simulator_provider_send_rejects_inbound_direction() -> None:
    provider = SimulatorProvider(lambda: "development-only")
    message = NormalizedMessage.model_validate(payload())
    with pytest.raises(ValueError, match="outbound messages only"):
        provider.send(message)


def test_simulator_provider_send_rejects_wrong_provider() -> None:
    provider = SimulatorProvider(lambda: "development-only")
    body = payload()
    body["direction"] = "outbound"
    body["provider"] = "bandwidth"
    message = NormalizedMessage.model_validate(body)
    with pytest.raises(ValueError, match="provider identity"):
        provider.send(message)


def test_simulator_provider_verify_webhook_reads_its_own_header() -> None:
    provider = SimulatorProvider(lambda: "development-only")
    good = ProviderWebhookRequest(body=b"{}", headers={"x-wwcx-signature": "development-only"})
    bad = ProviderWebhookRequest(body=b"{}", headers={"x-wwcx-signature": "wrong"})
    missing = ProviderWebhookRequest(body=b"{}", headers={})
    assert provider.verify_webhook(good) is True
    assert provider.verify_webhook(bad) is False
    assert provider.verify_webhook(missing) is False


def test_simulator_provider_normalize_webhook_round_trips() -> None:
    provider = SimulatorProvider(lambda: "development-only")
    request = ProviderWebhookRequest(body=json.dumps(payload()).encode(), headers={})
    message = provider.normalize_webhook(request)
    assert isinstance(message, NormalizedMessage)
    assert message.provider == "simulator"
    assert message.sender == "+16045550101"
