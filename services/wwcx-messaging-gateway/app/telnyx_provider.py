from __future__ import annotations

import base64
import json
import time
from datetime import datetime, timezone
from typing import Callable, Mapping

import httpx
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .models import Channel, DeliveryStatus, DeliveryStatusEvent, Direction, MediaItem, NormalizedMessage
from .providers import (
    MessagingProvider,
    ProviderConfigurationError,
    ProviderOutcomeUnknownError,
    ProviderRejectedError,
    ProviderSafeRetryError,
    ProviderWebhookRequest,
    SendResult,
)

TELNYX_API_BASE = "https://api.telnyx.com/v2"
TELNYX_SIGNATURE_HEADER = "telnyx-signature-ed25519"
TELNYX_TIMESTAMP_HEADER = "telnyx-timestamp"
TELNYX_REPLAY_WINDOW_SECONDS = 300


def _header(headers: Mapping[str, str], name: str) -> str | None:
    target = name.lower()
    for key, value in headers.items():
        if key.lower() == target:
            return value
    return None


def _parse_telnyx_public_key(value: str) -> Ed25519PublicKey:
    raw = value.strip()
    try:
        if len(raw) == 64:
            key_bytes = bytes.fromhex(raw)
        else:
            key_bytes = base64.b64decode(raw, validate=True)
    except (ValueError, TypeError) as exc:
        raise ProviderConfigurationError("Telnyx public key is malformed") from exc
    if len(key_bytes) != 32:
        raise ProviderConfigurationError("Telnyx public key must decode to 32 bytes")
    return Ed25519PublicKey.from_public_bytes(key_bytes)


def _event(request: ProviderWebhookRequest) -> tuple[dict[str, object], dict[str, object]]:
    try:
        envelope = json.loads(request.body)
    except json.JSONDecodeError as exc:
        raise ValueError("Telnyx webhook body is not valid JSON") from exc
    if not isinstance(envelope, dict):
        raise ValueError("Telnyx webhook envelope must be an object")
    data = envelope.get("data")
    if not isinstance(data, dict):
        raise ValueError("Telnyx webhook is missing data")
    payload = data.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("Telnyx webhook is missing data.payload")
    return data, payload


def _phone_number(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        candidate = value.get("phone_number")
        if isinstance(candidate, str):
            return candidate
    raise ValueError("Telnyx phone-number field is missing")


def _recipient_numbers(payload: Mapping[str, object]) -> list[str]:
    raw = payload.get("to")
    if not isinstance(raw, list) or not raw:
        raise ValueError("Telnyx webhook has no recipients")
    return [_phone_number(item) for item in raw]


def _occurred_at(data: Mapping[str, object]) -> datetime:
    raw = data.get("occurred_at")
    if not isinstance(raw, str):
        return datetime.now(timezone.utc)
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Telnyx occurred_at is malformed") from exc
    return parsed.astimezone(timezone.utc)


def _media_items(payload: Mapping[str, object]) -> list[MediaItem]:
    raw = payload.get("media")
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError("Telnyx media must be an array")
    items: list[MediaItem] = []
    for entry in raw[:16]:
        if not isinstance(entry, dict):
            raise ValueError("Telnyx media entry must be an object")
        url = entry.get("url")
        if not isinstance(url, str) or not url.startswith("https://"):
            raise ValueError("Telnyx media URL must use HTTPS")
        content_type = entry.get("content_type") if isinstance(entry.get("content_type"), str) else None
        digest = entry.get("sha256") if isinstance(entry.get("sha256"), str) else None
        items.append(MediaItem(url=url, content_type=content_type, sha256=digest))
    return items


class TelnyxProvider(MessagingProvider):
    """Credential-injected Telnyx SMS/MMS adapter.

    Source availability does not register or activate the adapter. The caller must
    explicitly provide a webhook public key and, for outbound submission, an API-key
    provider. No secret values are persisted by this class.
    """

    name = "telnyx"

    def __init__(
        self,
        webhook_public_key_provider: Callable[[], str],
        api_key_provider: Callable[[], str] | None = None,
        *,
        now_provider: Callable[[], float] = time.time,
        client_factory: Callable[[], httpx.Client] | None = None,
    ) -> None:
        self._webhook_public_key_provider = webhook_public_key_provider
        self._api_key_provider = api_key_provider
        self._now_provider = now_provider
        self._client_factory = client_factory or (
            lambda: httpx.Client(base_url=TELNYX_API_BASE, timeout=httpx.Timeout(10.0), follow_redirects=False)
        )

    def verify_webhook(self, request: ProviderWebhookRequest) -> bool:
        signature_text = _header(request.headers, TELNYX_SIGNATURE_HEADER)
        timestamp_text = _header(request.headers, TELNYX_TIMESTAMP_HEADER)
        if not signature_text or not timestamp_text:
            return False
        try:
            timestamp = int(timestamp_text)
        except ValueError:
            return False
        if abs(self._now_provider() - timestamp) > TELNYX_REPLAY_WINDOW_SECONDS:
            return False
        try:
            signature = base64.b64decode(signature_text, validate=True)
            public_key = _parse_telnyx_public_key(self._webhook_public_key_provider())
            signed = timestamp_text.encode("ascii") + b"|" + request.body
            public_key.verify(signature, signed)
        except (ValueError, InvalidSignature, ProviderConfigurationError):
            return False
        return True

    def normalize_webhook(self, request: ProviderWebhookRequest) -> NormalizedMessage:
        data, payload = _event(request)
        if data.get("event_type") != "message.received":
            raise ValueError("Telnyx inbound normalizer requires message.received")
        event_id = data.get("id")
        if not isinstance(event_id, str) or not event_id:
            raise ValueError("Telnyx webhook event id is missing")
        media = _media_items(payload)
        text = payload.get("text") if isinstance(payload.get("text"), str) else ""
        return NormalizedMessage(
            provider=self.name,
            provider_event_id=event_id,
            direction=Direction.INBOUND,
            channel=Channel.MMS if media else Channel.SMS,
            **{"from": _phone_number(payload.get("from")), "to": _recipient_numbers(payload)},
            text=text,
            media=media,
            occurred_at=_occurred_at(data),
        )

    def normalize_delivery_webhook(self, request: ProviderWebhookRequest) -> DeliveryStatusEvent:
        data, payload = _event(request)
        if data.get("event_type") != "message.finalized":
            raise ValueError("Telnyx delivery normalizer requires message.finalized")
        event_id = data.get("id")
        message_id = payload.get("id")
        if not isinstance(event_id, str) or not event_id:
            raise ValueError("Telnyx delivery event id is missing")
        if not isinstance(message_id, str) or not message_id:
            raise ValueError("Telnyx provider message id is missing")

        raw_status: str | None = None
        recipient_statuses = payload.get("to")
        if isinstance(recipient_statuses, list) and recipient_statuses:
            first = recipient_statuses[0]
            if isinstance(first, dict) and isinstance(first.get("status"), str):
                raw_status = first["status"]
        if raw_status is None and isinstance(payload.get("status"), str):
            raw_status = payload["status"]
        if raw_status is None:
            raise ValueError("Telnyx finalized callback has no delivery status")

        status_map = {
            "delivered": DeliveryStatus.DELIVERED,
            "delivery_failed": DeliveryStatus.FAILED,
            "failed": DeliveryStatus.FAILED,
            "delivery_unconfirmed": DeliveryStatus.UNDELIVERED,
            "undelivered": DeliveryStatus.UNDELIVERED,
        }
        normalized = status_map.get(raw_status.lower())
        if normalized is None:
            raise ValueError("Telnyx finalized delivery status is not terminal")
        return DeliveryStatusEvent(
            provider=self.name,
            provider_event_id=event_id,
            provider_message_id=message_id,
            status=normalized,
            occurred_at=_occurred_at(data),
            raw_status=raw_status,
        )

    def send(self, message: NormalizedMessage) -> SendResult:
        if message.provider != self.name:
            raise ValueError("outbound provider identity does not match Telnyx adapter")
        if message.direction != Direction.OUTBOUND:
            raise ValueError("Telnyx send accepts outbound messages only")
        if self._api_key_provider is None:
            raise ProviderConfigurationError("Telnyx outbound API key is not configured")
        api_key = self._api_key_provider().strip()
        if not api_key:
            raise ProviderConfigurationError("Telnyx outbound API key is empty")

        body: dict[str, object] = {"from": message.sender, "to": message.recipients, "text": message.text}
        if message.media:
            body["media_urls"] = [item.url for item in message.media]

        try:
            with self._client_factory() as client:
                response = client.post(
                    "/messages",
                    json=body,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                )
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            raise ProviderSafeRetryError("Telnyx connection failed before submission") from exc
        except (httpx.ReadTimeout, httpx.WriteTimeout, httpx.RemoteProtocolError) as exc:
            raise ProviderOutcomeUnknownError("Telnyx submission outcome is uncertain") from exc

        if 400 <= response.status_code < 500:
            raise ProviderRejectedError(f"Telnyx rejected outbound request with HTTP {response.status_code}")
        if response.status_code >= 500:
            raise ProviderOutcomeUnknownError(f"Telnyx returned HTTP {response.status_code} after submission")

        try:
            result = response.json()
            data = result["data"]
            provider_message_id = data["id"]
        except (ValueError, KeyError, TypeError) as exc:
            raise ProviderOutcomeUnknownError("Telnyx success response lacks a message id") from exc
        if not isinstance(provider_message_id, str) or not provider_message_id:
            raise ProviderOutcomeUnknownError("Telnyx success response has invalid message id")
        return SendResult(provider_message_id=provider_message_id, accepted=True)
