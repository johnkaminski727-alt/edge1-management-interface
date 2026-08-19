from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, Mapping

from .models import DeliveryStatusEvent, Direction, NormalizedMessage


@dataclass(frozen=True)
class SendResult:
    provider_message_id: str
    accepted: bool


class ProviderSafeRetryError(RuntimeError):
    """Provider adapter guarantees the message was not accepted/submitted.

    Only this explicit exception authorizes the worker to place a claimed job
    back into the retry queue. Any other exception is treated as an uncertain
    provider outcome and must remain claimed for reconciliation rather than
    risking a duplicate live message.
    """


@dataclass(frozen=True)
class ProviderWebhookRequest:
    """Generic inbound webhook request passed to a MessagingProvider."""

    body: bytes
    headers: Mapping[str, str]


class MessagingProvider(ABC):
    """Carrier-neutral boundary for inbound, delivery, and outbound operations."""

    name: str

    @abstractmethod
    def verify_webhook(self, request: ProviderWebhookRequest) -> bool:
        """Return True only for authentic callbacks inside the provider replay window.

        Authentication, signature verification, timestamp freshness, and replay-
        window enforcement are adapter obligations. The shared route deliberately
        does not invent provider-specific header or timing rules.
        """
        raise NotImplementedError

    @abstractmethod
    def normalize_webhook(self, request: ProviderWebhookRequest) -> NormalizedMessage:
        """Convert a provider-specific inbound message callback."""
        raise NotImplementedError

    @abstractmethod
    def normalize_delivery_webhook(self, request: ProviderWebhookRequest) -> DeliveryStatusEvent:
        """Convert a provider-specific asynchronous delivery/status callback."""
        raise NotImplementedError

    @abstractmethod
    def send(self, message: NormalizedMessage) -> SendResult:
        """Submit one outbound message assigned to this provider.

        Raise ProviderSafeRetryError only when the adapter can prove the
        provider did not accept or submit the message. Other exceptions are
        treated as outcome-uncertain and are not automatically retried.
        """
        raise NotImplementedError


class SimulatorProvider(MessagingProvider):
    """Reference adapter used only for local/private simulator testing."""

    name = "simulator"

    def __init__(self, token_provider: Callable[[], str]) -> None:
        self._token_provider = token_provider

    def verify_webhook(self, request: ProviderWebhookRequest) -> bool:
        return request.headers.get("x-wwcx-signature") == self._token_provider()

    def normalize_webhook(self, request: ProviderWebhookRequest) -> NormalizedMessage:
        payload = json.loads(request.body)
        message = NormalizedMessage.model_validate(payload)
        if message.provider != self.name:
            raise ValueError("webhook provider identity does not match adapter")
        if message.direction != Direction.INBOUND:
            raise ValueError("webhook normalization accepts inbound messages only")
        return message

    def normalize_delivery_webhook(self, request: ProviderWebhookRequest) -> DeliveryStatusEvent:
        event = DeliveryStatusEvent.model_validate_json(request.body)
        if event.provider != self.name:
            raise ValueError("delivery provider identity does not match adapter")
        return event

    def send(self, message: NormalizedMessage) -> SendResult:
        if message.provider != self.name:
            raise ValueError("outbound provider identity does not match adapter")
        if message.direction != Direction.OUTBOUND:
            raise ValueError("provider send accepts outbound messages only")
        return SendResult(provider_message_id=f"sim-{message.event_id}", accepted=True)


def build_provider_registry(token_provider: Callable[[], str]) -> dict[str, MessagingProvider]:
    """Build the provider name -> adapter registry used by the gateway."""
    return {"simulator": SimulatorProvider(token_provider)}
