import base64
import json

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.models import DeliveryStatus, Direction, NormalizedMessage
from app.providers import (
    ProviderConfigurationError,
    ProviderOutcomeUnknownError,
    ProviderRejectedError,
    ProviderSafeRetryError,
    ProviderWebhookRequest,
)
from app.telnyx_provider import TelnyxProvider


NOW = 1_787_217_000


def inbound_envelope(*, event_type: str = "message.received", media: list[dict[str, object]] | None = None) -> dict[str, object]:
    return {
        "data": {
            "id": "evt-telnyx-001",
            "event_type": event_type,
            "occurred_at": "2026-08-20T09:00:00Z",
            "payload": {
                "id": "msg-telnyx-001",
                "from": {"phone_number": "+13065550101"},
                "to": [{"phone_number": "+13065550102", "status": "delivered"}],
                "text": "hello from telnyx",
                "media": media or [],
            },
        }
    }


def outbound_message() -> NormalizedMessage:
    return NormalizedMessage(
        provider="telnyx",
        provider_event_id="outbound-local-001",
        direction=Direction.OUTBOUND,
        channel="sms",
        **{"from": "+13065550102", "to": ["+13065550101"]},
        text="hello outbound",
    )


def signed_request(body: bytes, private_key: Ed25519PrivateKey, timestamp: int = NOW) -> ProviderWebhookRequest:
    stamp = str(timestamp)
    signature = private_key.sign(stamp.encode("ascii") + b"|" + body)
    return ProviderWebhookRequest(
        body=body,
        headers={
            "Telnyx-Signature-Ed25519": base64.b64encode(signature).decode("ascii"),
            "Telnyx-Timestamp": stamp,
        },
    )


def provider_with_key(private_key: Ed25519PrivateKey, **kwargs: object) -> TelnyxProvider:
    public_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return TelnyxProvider(lambda: public_bytes.hex(), now_provider=lambda: NOW, **kwargs)


class FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, object] | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}

    def json(self) -> dict[str, object]:
        return self._payload


class FakeClient:
    def __init__(self, response: FakeResponse | None = None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.last_request: dict[str, object] | None = None

    def __enter__(self) -> "FakeClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def post(self, path: str, *, json: dict[str, object], headers: dict[str, str]) -> FakeResponse:
        self.last_request = {"path": path, "json": json, "headers": headers}
        if self.error is not None:
            raise self.error
        assert self.response is not None
        return self.response


def test_verify_webhook_accepts_valid_ed25519_signature() -> None:
    private_key = Ed25519PrivateKey.generate()
    body = json.dumps(inbound_envelope(), separators=(",", ":")).encode()
    provider = provider_with_key(private_key)
    assert provider.verify_webhook(signed_request(body, private_key)) is True


def test_verify_webhook_rejects_stale_or_tampered_request() -> None:
    private_key = Ed25519PrivateKey.generate()
    body = json.dumps(inbound_envelope(), separators=(",", ":")).encode()
    provider = provider_with_key(private_key)
    assert provider.verify_webhook(signed_request(body, private_key, NOW - 301)) is False
    request = signed_request(body, private_key)
    tampered = ProviderWebhookRequest(body=body + b" ", headers=request.headers)
    assert provider.verify_webhook(tampered) is False


def test_verify_webhook_fails_closed_for_bad_public_key() -> None:
    provider = TelnyxProvider(lambda: "not-a-key", now_provider=lambda: NOW)
    request = ProviderWebhookRequest(
        body=b"{}",
        headers={"telnyx-signature-ed25519": base64.b64encode(b"x" * 64).decode(), "telnyx-timestamp": str(NOW)},
    )
    assert provider.verify_webhook(request) is False


def test_normalize_inbound_sms() -> None:
    private_key = Ed25519PrivateKey.generate()
    provider = provider_with_key(private_key)
    body = json.dumps(inbound_envelope()).encode()
    message = provider.normalize_webhook(ProviderWebhookRequest(body=body, headers={}))
    assert message.provider == "telnyx"
    assert message.provider_event_id == "evt-telnyx-001"
    assert message.direction == Direction.INBOUND
    assert message.channel.value == "sms"
    assert message.sender == "+13065550101"
    assert message.recipients == ["+13065550102"]


def test_normalize_inbound_mms_preserves_provider_reference_but_does_not_fetch() -> None:
    private_key = Ed25519PrivateKey.generate()
    provider = provider_with_key(private_key)
    body = json.dumps(
        inbound_envelope(
            media=[{"url": "https://example.telnyx.invalid/media/1", "content_type": "image/jpeg"}]
        )
    ).encode()
    message = provider.normalize_webhook(ProviderWebhookRequest(body=body, headers={}))
    assert message.channel.value == "mms"
    assert len(message.media) == 1
    assert message.media[0].sha256 is None


def test_normalize_delivery_finalized_maps_terminal_status() -> None:
    private_key = Ed25519PrivateKey.generate()
    provider = provider_with_key(private_key)
    body = json.dumps(inbound_envelope(event_type="message.finalized")).encode()
    event = provider.normalize_delivery_webhook(ProviderWebhookRequest(body=body, headers={}))
    assert event.provider_message_id == "msg-telnyx-001"
    assert event.status == DeliveryStatus.DELIVERED
    assert event.raw_status == "delivered"


def test_send_requires_injected_api_key_and_never_registers_itself() -> None:
    private_key = Ed25519PrivateKey.generate()
    provider = provider_with_key(private_key)
    with pytest.raises(ProviderConfigurationError):
        provider.send(outbound_message())


def test_send_success_returns_provider_message_id() -> None:
    private_key = Ed25519PrivateKey.generate()
    client = FakeClient(FakeResponse(200, {"data": {"id": "msg-accepted-001"}}))
    provider = provider_with_key(
        private_key,
        api_key_provider=lambda: "test-only-api-key",
        client_factory=lambda: client,
    )
    result = provider.send(outbound_message())
    assert result.accepted is True
    assert result.provider_message_id == "msg-accepted-001"
    assert client.last_request is not None
    assert client.last_request["path"] == "/messages"
    assert client.last_request["headers"]["Authorization"] == "Bearer test-only-api-key"


def test_send_4xx_is_explicit_rejection_not_uncertain_retry() -> None:
    private_key = Ed25519PrivateKey.generate()
    provider = provider_with_key(
        private_key,
        api_key_provider=lambda: "test-only-api-key",
        client_factory=lambda: FakeClient(FakeResponse(400, {"errors": []})),
    )
    with pytest.raises(ProviderRejectedError):
        provider.send(outbound_message())


def test_send_connect_failure_is_safe_retry() -> None:
    private_key = Ed25519PrivateKey.generate()
    request = httpx.Request("POST", "https://api.telnyx.com/v2/messages")
    provider = provider_with_key(
        private_key,
        api_key_provider=lambda: "test-only-api-key",
        client_factory=lambda: FakeClient(error=httpx.ConnectError("connect failed", request=request)),
    )
    with pytest.raises(ProviderSafeRetryError):
        provider.send(outbound_message())


def test_send_read_timeout_is_outcome_unknown() -> None:
    private_key = Ed25519PrivateKey.generate()
    request = httpx.Request("POST", "https://api.telnyx.com/v2/messages")
    provider = provider_with_key(
        private_key,
        api_key_provider=lambda: "test-only-api-key",
        client_factory=lambda: FakeClient(error=httpx.ReadTimeout("timed out", request=request)),
    )
    with pytest.raises(ProviderOutcomeUnknownError):
        provider.send(outbound_message())


def test_send_server_error_is_outcome_unknown() -> None:
    private_key = Ed25519PrivateKey.generate()
    provider = provider_with_key(
        private_key,
        api_key_provider=lambda: "test-only-api-key",
        client_factory=lambda: FakeClient(FakeResponse(503, {"errors": []})),
    )
    with pytest.raises(ProviderOutcomeUnknownError):
        provider.send(outbound_message())
