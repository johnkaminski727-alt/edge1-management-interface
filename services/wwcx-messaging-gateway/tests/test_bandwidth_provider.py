import base64
import json

import httpx
import pytest

from app.bandwidth_provider import BANDWIDTH_BASIC_CHALLENGE, BandwidthProvider
from app.models import DeliveryStatus, Direction, NormalizedMessage
from app.providers import (
    ProviderConfigurationError,
    ProviderOutcomeUnknownError,
    ProviderRejectedError,
    ProviderSafeRetryError,
    ProviderWebhookRequest,
)


def basic_header(username: str, password: str) -> str:
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return f"Basic {token}"


def inbound_event(*, media: list[str] | None = None, channel: str | None = None) -> list[dict[str, object]]:
    message: dict[str, object] = {
        "id": "bw-msg-001",
        "owner": "+13065550102",
        "applicationId": "app-001",
        "time": "2026-08-20T14:00:00Z",
        "direction": "in",
        "to": ["+13065550102"],
        "from": "+13065550101",
        "text": "hello from bandwidth",
    }
    if media is not None:
        message["media"] = media
    if channel is not None:
        message["channel"] = channel
    return [{
        "time": "2026-08-20T14:00:01Z",
        "type": "message-received",
        "to": "+13065550102",
        "description": "Incoming message received",
        "message": message,
    }]


def delivery_event(event_type: str, *, error_code: int | None = None) -> list[dict[str, object]]:
    event: dict[str, object] = {
        "time": "2026-08-20T14:01:00Z",
        "type": event_type,
        "to": "+13065550101",
        "description": event_type,
        "message": {
            "id": "bw-msg-out-001",
            "owner": "+13065550102",
            "applicationId": "app-001",
            "time": "2026-08-20T14:00:59Z",
            "direction": "out",
            "to": ["+13065550101"],
            "from": "+13065550102",
            "text": "",
        },
    }
    if error_code is not None:
        event["errorCode"] = error_code
    return [event]


def outbound_message(*, recipients: list[str] | None = None) -> NormalizedMessage:
    return NormalizedMessage(
        provider="bandwidth",
        provider_event_id="outbound-local-001",
        direction=Direction.OUTBOUND,
        channel="sms",
        **{"from": "+13065550102", "to": recipients or ["+13065550101"]},
        text="hello outbound",
    )


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


def provider(**kwargs: object) -> BandwidthProvider:
    return BandwidthProvider(lambda: "callback-user", lambda: "callback-pass", **kwargs)


def outbound_provider(client: FakeClient) -> BandwidthProvider:
    return provider(
        account_id_provider=lambda: "1234567",
        api_username_provider=lambda: "api-user",
        api_password_provider=lambda: "api-pass",
        application_id_provider=lambda: "app-001",
        client_factory=lambda: client,
    )


def test_verify_webhook_accepts_valid_basic_auth() -> None:
    request = ProviderWebhookRequest(body=b"[]", headers={"Authorization": basic_header("callback-user", "callback-pass")})
    assert provider().verify_webhook(request) is True


def test_verify_webhook_rejects_missing_malformed_or_wrong_auth() -> None:
    adapter = provider()
    assert adapter.verify_webhook(ProviderWebhookRequest(body=b"[]", headers={})) is False
    assert adapter.verify_webhook(ProviderWebhookRequest(body=b"[]", headers={"Authorization": "Bearer nope"})) is False
    assert adapter.verify_webhook(ProviderWebhookRequest(body=b"[]", headers={"Authorization": basic_header("callback-user", "wrong")})) is False


def test_webhook_auth_failure_advertises_basic_challenge() -> None:
    assert provider().webhook_auth_failure_headers() == {"WWW-Authenticate": BANDWIDTH_BASIC_CHALLENGE}


def test_normalize_inbound_sms_array_payload() -> None:
    message = provider().normalize_webhook(ProviderWebhookRequest(body=json.dumps(inbound_event()).encode(), headers={}))
    assert message.provider == "bandwidth"
    assert message.provider_event_id == "bw-msg-001"
    assert message.direction == Direction.INBOUND
    assert message.channel.value == "sms"
    assert message.sender == "+13065550101"
    assert message.recipients == ["+13065550102"]


def test_normalize_inbound_mms_preserves_allowlisted_media_reference() -> None:
    url = "https://messaging.bandwidth.com/api/v2/users/1234567/media/bw-msg-001/0/photo.jpg"
    message = provider().normalize_webhook(
        ProviderWebhookRequest(body=json.dumps(inbound_event(media=[url], channel="mms")).encode(), headers={})
    )
    assert message.channel.value == "mms"
    assert message.media[0].url == url
    assert message.media[0].sha256 is None


def test_normalize_inbound_rejects_non_bandwidth_media_origin() -> None:
    with pytest.raises(ValueError, match="origin"):
        provider().normalize_webhook(
            ProviderWebhookRequest(
                body=json.dumps(inbound_event(media=["https://example.invalid/media/a.jpg"], channel="mms")).encode(),
                headers={},
            )
        )


def test_normalize_rejects_multi_event_batch_to_avoid_silent_loss() -> None:
    events = inbound_event() + inbound_event()
    with pytest.raises(ValueError, match="exactly one"):
        provider().normalize_webhook(ProviderWebhookRequest(body=json.dumps(events).encode(), headers={}))


def test_normalize_delivery_maps_terminal_statuses() -> None:
    delivered = provider().normalize_delivery_webhook(
        ProviderWebhookRequest(body=json.dumps(delivery_event("message-delivered")).encode(), headers={})
    )
    failed = provider().normalize_delivery_webhook(
        ProviderWebhookRequest(body=json.dumps(delivery_event("message-failed", error_code=4700)).encode(), headers={})
    )
    assert delivered.status == DeliveryStatus.DELIVERED
    assert failed.status == DeliveryStatus.FAILED
    assert failed.raw_status == "message-failed:4700"
    assert delivered.provider_message_id == "bw-msg-out-001"


def test_normalize_delivery_rejects_intermediate_status() -> None:
    with pytest.raises(ValueError, match="terminal"):
        provider().normalize_delivery_webhook(
            ProviderWebhookRequest(body=json.dumps(delivery_event("message-sent")).encode(), headers={})
        )


def test_send_requires_injected_outbound_configuration() -> None:
    with pytest.raises(ProviderConfigurationError):
        provider().send(outbound_message())


def test_send_success_uses_bandwidth_v2_path_and_basic_auth() -> None:
    client = FakeClient(FakeResponse(202, {"id": "bw-accepted-001"}))
    result = outbound_provider(client).send(outbound_message())
    assert result.accepted is True
    assert result.provider_message_id == "bw-accepted-001"
    assert client.last_request is not None
    assert client.last_request["path"] == "/api/v2/users/1234567/messages"
    assert client.last_request["json"]["applicationId"] == "app-001"
    assert client.last_request["headers"]["Authorization"] == basic_header("api-user", "api-pass")


def test_send_more_than_ten_recipients_is_rejected_before_provider_call() -> None:
    client = FakeClient(FakeResponse(202, {"id": "should-not-send"}))
    with pytest.raises(ProviderRejectedError, match="at most 10"):
        outbound_provider(client).send(outbound_message(recipients=[f"+13065550{i:03d}" for i in range(11)]))
    assert client.last_request is None


def test_send_permanent_4xx_is_explicit_rejection() -> None:
    with pytest.raises(ProviderRejectedError):
        outbound_provider(FakeClient(FakeResponse(400, {}))).send(outbound_message())


def test_send_rate_limit_is_safe_retry() -> None:
    with pytest.raises(ProviderSafeRetryError):
        outbound_provider(FakeClient(FakeResponse(429, {}))).send(outbound_message())


def test_send_connect_failure_is_safe_retry() -> None:
    request = httpx.Request("POST", "https://messaging.bandwidth.com/api/v2/users/1234567/messages")
    with pytest.raises(ProviderSafeRetryError):
        outbound_provider(FakeClient(error=httpx.ConnectError("connect failed", request=request))).send(outbound_message())


def test_send_read_timeout_is_outcome_unknown() -> None:
    request = httpx.Request("POST", "https://messaging.bandwidth.com/api/v2/users/1234567/messages")
    with pytest.raises(ProviderOutcomeUnknownError):
        outbound_provider(FakeClient(error=httpx.ReadTimeout("timed out", request=request))).send(outbound_message())


def test_send_server_error_is_safe_retry() -> None:
    with pytest.raises(ProviderSafeRetryError):
        outbound_provider(FakeClient(FakeResponse(503, {}))).send(outbound_message())
