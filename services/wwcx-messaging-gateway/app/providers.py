from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, Mapping

from .models import Direction, NormalizedMessage


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
    """Generic inbound webhook request passed to a MessagingProvider.

    Deliberately carries only the raw body and headers -- no assumption
    about which header names carry authentication/signature information
    (that varies per provider: Telnyx uses telnyx-signature-ed25519 +
    telnyx-timestamp, Bandwidth may use HTTP Basic Auth, the simulator
    reuses a shared token header) and no assumption about payload shape
    (Bandwidth messaging callbacks are JSON arrays, not single objects).
    `headers` is case-insensitive, matching Starlette's Headers behavior.
    """

    body: bytes
    headers: Mapping[str, str]


class MessagingProvider(ABC):
    """Boundary implemented by Telnyx, Bandwidth, and simulator adapters.

    Adapter implementations are responsible for preserving provider identity
    and direction at the boundary. Inbound webhook normalization must never
    manufacture another provider's identity or an outbound message, and send
    implementations must reject messages assigned to a different provider or
    carrying a non-outbound direction.
    """

    name: str

    @abstractmethod
    def verify_webhook(self, request: ProviderWebhookRequest) -> bool:
        """Return True only for authentic, timely provider callbacks.

        Each provider extracts and validates its own authentication scheme
        from request.headers / request.body -- the shared dispatch route
        does not know or assume which headers matter.
        """
        raise NotImplementedError

    @abstractmethod
    def normalize_webhook(self, request: ProviderWebhookRequest) -> NormalizedMessage:
        """Convert a provider-specific webhook body into the WW.CX message model.

        Each provider parses request.body however its own callback format
        requires (a single JSON object, a JSON array, form-encoded, etc.) --
        the shared dispatch route does not assume a dict payload. The returned
        message must identify this adapter's provider and be inbound.
        """
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
    """Reference MessagingProvider implementation used for local/dev testing.

    A real carrier adapter implements this interface with its own signature
    verification, payload normalization, and send semantics. The simulator
    deliberately uses a static development token and never represents a real
    carrier security model.
    """

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

    def send(self, message: NormalizedMessage) -> SendResult:
        if message.provider != self.name:
            raise ValueError("outbound provider identity does not match adapter")
        if message.direction != Direction.OUTBOUND:
            raise ValueError("provider send accepts outbound messages only")
        return SendResult(provider_message_id=f"sim-{message.event_id}", accepted=True)


def build_provider_registry(token_provider: Callable[[], str]) -> dict[str, MessagingProvider]:
    """Build the provider name -> adapter registry used by the gateway."""
    return {"simulator": SimulatorProvider(token_provider)}
