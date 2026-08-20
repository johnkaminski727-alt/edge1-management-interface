from __future__ import annotations

import base64
import hmac
import json
import re
from datetime import datetime, timezone
from typing import Callable, Mapping
from urllib.parse import urlparse

import httpx

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

BANDWIDTH_API_ORIGIN = "https://messaging.bandwidth.com"
BANDWIDTH_MEDIA_HOST = "messaging.bandwidth.com"
BANDWIDTH_BASIC_CHALLENGE = 'Basic realm="WW.CX Bandwidth Messaging"'
_ACCOUNT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


def _header(headers: Mapping[str, str], name: str) -> str | None:
    target = name.lower()
    for key, value in headers.items():
        if key.lower() == target:
            return value
    return None


def _required_value(provider: Callable[[], str] | None, label: str) -> str:
    if provider is None:
        raise ProviderConfigurationError(f"Bandwidth {label} is not configured")
    value = provider().strip()
    if not value:
        raise ProviderConfigurationError(f"Bandwidth {label} is empty")
    return value


def _basic_authorization(username: str, password: str) -> str:
    token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    return f"Basic {token}"


def _basic_credentials(value: str | None) -> tuple[str, str] | None:
    if not value:
        return None
    scheme, separator, token = value.partition(" ")
    if not separator or scheme.lower() != "basic" or not token:
        return None
    try:
        decoded = base64.b64decode(token, validate=True).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None
    username, separator, password = decoded.partition(":")
    if not separator:
        return None
    return username, password


def _single_event(request: ProviderWebhookRequest) -> dict[str, object]:
    try:
        envelope = json.loads(request.body)
    except json.JSONDecodeError as exc:
        raise ValueError("Bandwidth webhook body is not valid JSON") from exc
    if not isinstance(envelope, list) or len(envelope) != 1:
        raise ValueError("Bandwidth webhook must contain exactly one callback event")
    event = envelope[0]
    if not isinstance(event, dict):
        raise ValueError("Bandwidth callback event must be an object")
    return event


def _message(event: Mapping[str, object]) -> dict[str, object]:
    message = event.get("message")
    if not isinstance(message, dict):
        raise ValueError("Bandwidth callback is missing message")
    return message


def _occurred_at(event: Mapping[str, object]) -> datetime:
    raw = event.get("time")
    if not isinstance(raw, str) or not raw:
        raise ValueError("Bandwidth callback time is missing")
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Bandwidth callback time is malformed") from exc
    return parsed.astimezone(timezone.utc)


def _recipients(message: Mapping[str, object]) -> list[str]:
    raw = message.get("to")
    if not isinstance(raw, list) or not raw:
        raise ValueError("Bandwidth message has no recipients")
    recipients: list[str] = []
    for value in raw:
        if not isinstance(value, str) or not value:
            raise ValueError("Bandwidth recipient is invalid")
        recipients.append(value)
    return recipients


def _validate_media_url(value: str) -> None:
    parsed = urlparse(value)
    if parsed.scheme != "https" or parsed.hostname != BANDWIDTH_MEDIA_HOST:
        raise ValueError("Bandwidth media URL origin is not allowlisted")
    if parsed.username or parsed.password or parsed.fragment:
        raise ValueError("Bandwidth media URL contains disallowed components")
    if parsed.port not in {None, 443}:
        raise ValueError("Bandwidth media URL uses a disallowed port")
    if not parsed.path.startswith("/api/v2/users/") or "/media/" not in parsed.path:
        raise ValueError("Bandwidth media URL path is invalid")
    if len(parsed.path) > 4096:
        raise ValueError("Bandwidth media URL path is too long")


def _media_items(message: Mapping[str, object]) -> list[MediaItem]:
    raw = message.get("media")
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError("Bandwidth media must be an array")
    items: list[MediaItem] = []
    for value in raw[:16]:
        if not isinstance(value, str):
            raise ValueError("Bandwidth media URL must be text")
        _validate_media_url(value)
        items.append(MediaItem(url=value))
    return items


def _message_id(message: Mapping[str, object]) -> str:
    value = message.get("id")
    if not isinstance(value, str) or not value:
        raise ValueError("Bandwidth message id is missing")
    return value


class BandwidthProvider(MessagingProvider):
    """Credential-injected Bandwidth SMS/MMS adapter.

    Bandwidth Messaging-V2 callback authentication uses configured HTTP Basic
    credentials and a standards-compliant 401 challenge. The adapter remains
    unregistered until a separate activation step explicitly adds it to the
    live provider registry.
    """

    name = "bandwidth"

    def __init__(
        self,
        webhook_username_provider: Callable[[], str],
        webhook_password_provider: Callable[[], str],
        *,
        account_id_provider: Callable[[], str] | None = None,
        api_username_provider: Callable[[], str] | None = None,
        api_password_provider: Callable[[], str] | None = None,
        application_id_provider: Callable[[], str] | None = None,
        client_factory: Callable[[], httpx.Client] | None = None,
    ) -> None:
        self._webhook_username_provider = webhook_username_provider
        self._webhook_password_provider = webhook_password_provider
        self._account_id_provider = account_id_provider
        self._api_username_provider = api_username_provider
        self._api_password_provider = api_password_provider
        self._application_id_provider = application_id_provider
        self._client_factory = client_factory or (
            lambda: httpx.Client(
                base_url=BANDWIDTH_API_ORIGIN,
                timeout=httpx.Timeout(10.0),
                follow_redirects=False,
            )
        )

    def verify_webhook(self, request: ProviderWebhookRequest) -> bool:
        credentials = _basic_credentials(_header(request.headers, "authorization"))
        if credentials is None:
            return False
        try:
            expected_username = _required_value(self._webhook_username_provider, "webhook username")
            expected_password = _required_value(self._webhook_password_provider, "webhook password")
        except ProviderConfigurationError:
            return False
        provided = f"{credentials[0]}:{credentials[1]}".encode("utf-8")
        expected = f"{expected_username}:{expected_password}".encode("utf-8")
        return hmac.compare_digest(provided, expected)

    def webhook_auth_failure_headers(self) -> dict[str, str]:
        return {"WWW-Authenticate": BANDWIDTH_BASIC_CHALLENGE}

    def normalize_webhook(self, request: ProviderWebhookRequest) -> NormalizedMessage:
        event = _single_event(request)
        if event.get("type") != "message-received":
            raise ValueError("Bandwidth inbound normalizer requires message-received")
        message = _message(event)
        if message.get("direction") not in {None, "in"}:
            raise ValueError("Bandwidth inbound callback direction is not inbound")
        sender = message.get("from")
        if not isinstance(sender, str) or not sender:
            raise ValueError("Bandwidth sender is missing")
        media = _media_items(message)
        raw_channel = message.get("channel")
        if isinstance(raw_channel, str) and raw_channel.lower() not in {"sms", "mms"}:
            raise ValueError("Bandwidth channel is unsupported")
        channel = Channel.MMS if media or (isinstance(raw_channel, str) and raw_channel.lower() == "mms") else Channel.SMS
        text = message.get("text") if isinstance(message.get("text"), str) else ""
        return NormalizedMessage(
            provider=self.name,
            provider_event_id=_message_id(message),
            direction=Direction.INBOUND,
            channel=channel,
            **{"from": sender, "to": _recipients(message)},
            text=text,
            media=media,
            occurred_at=_occurred_at(event),
        )

    def normalize_delivery_webhook(self, request: ProviderWebhookRequest) -> DeliveryStatusEvent:
        event = _single_event(request)
        event_type = event.get("type")
        status_map = {
            "message-delivered": DeliveryStatus.DELIVERED,
            "message-failed": DeliveryStatus.FAILED,
        }
        if event_type not in status_map:
            raise ValueError("Bandwidth delivery normalizer requires a terminal callback")
        message = _message(event)
        if message.get("direction") not in {None, "out"}:
            raise ValueError("Bandwidth delivery callback direction is not outbound")
        message_id = _message_id(message)
        recipient = event.get("to")
        recipient_key = recipient if isinstance(recipient, str) and recipient else "unknown"
        raw_status = str(event_type)
        error_code = event.get("errorCode")
        if event_type == "message-failed" and isinstance(error_code, int):
            raw_status = f"{event_type}:{error_code}"
        return DeliveryStatusEvent(
            provider=self.name,
            provider_event_id=f"{event_type}:{message_id}:{recipient_key}",
            provider_message_id=message_id,
            status=status_map[str(event_type)],
            occurred_at=_occurred_at(event),
            raw_status=raw_status,
        )

    def send(self, message: NormalizedMessage) -> SendResult:
        if message.provider != self.name:
            raise ValueError("outbound provider identity does not match Bandwidth adapter")
        if message.direction != Direction.OUTBOUND:
            raise ValueError("Bandwidth send accepts outbound messages only")
        if len(message.recipients) > 10:
            raise ProviderRejectedError("Bandwidth outbound messages support at most 10 recipients")

        account_id = _required_value(self._account_id_provider, "account id")
        if not _ACCOUNT_ID_RE.fullmatch(account_id):
            raise ProviderConfigurationError("Bandwidth account id is malformed")
        api_username = _required_value(self._api_username_provider, "API username")
        api_password = _required_value(self._api_password_provider, "API password")
        application_id = _required_value(self._application_id_provider, "application id")

        body: dict[str, object] = {
            "from": message.sender,
            "to": message.recipients,
            "text": message.text,
            "applicationId": application_id,
        }
        if message.media:
            body["media"] = [item.url for item in message.media]

        try:
            with self._client_factory() as client:
                response = client.post(
                    f"/api/v2/users/{account_id}/messages",
                    json=body,
                    headers={
                        "Authorization": _basic_authorization(api_username, api_password),
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                )
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            raise ProviderSafeRetryError("Bandwidth connection failed before submission") from exc
        except (httpx.ReadTimeout, httpx.WriteTimeout, httpx.ReadError, httpx.WriteError, httpx.RemoteProtocolError) as exc:
            raise ProviderOutcomeUnknownError("Bandwidth submission outcome is uncertain") from exc

        if response.status_code == 429 or response.status_code >= 500:
            raise ProviderSafeRetryError(
                f"Bandwidth confirmed outbound message was not sent (HTTP {response.status_code})"
            )
        if 400 <= response.status_code < 500:
            raise ProviderRejectedError(f"Bandwidth rejected outbound request with HTTP {response.status_code}")
        if response.status_code < 200 or response.status_code >= 300:
            raise ProviderOutcomeUnknownError(f"Bandwidth returned unexpected HTTP {response.status_code}")

        try:
            result = response.json()
            provider_message_id = result["id"]
        except (ValueError, KeyError, TypeError) as exc:
            raise ProviderOutcomeUnknownError("Bandwidth success response lacks a message id") from exc
        if not isinstance(provider_message_id, str) or not provider_message_id:
            raise ProviderOutcomeUnknownError("Bandwidth success response has invalid message id")
        return SendResult(provider_message_id=provider_message_id, accepted=True)
