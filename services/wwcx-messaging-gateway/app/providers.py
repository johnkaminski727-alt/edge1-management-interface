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
        """Submit one outbound message assigned to this provider."""
        raise NotImplementedError


class SimulatorProvider(MessagingProvider):
    """Reference MessagingProvider implementation used for local/dev testing.

    This is the first concrete implementation of the abstraction above --
    previously the ABC existed but nothing used it; the simulator intake
    endpoint (/v1/simulator/messages) accepted NormalizedMessage bodies
    directly, bypassing verify_webhook/normalize_webhook entirely.

    A real carrier adapter (Telnyx, Bandwidth, etc.) implements this same
    interface with its own header-based signature verification and its own
    payload parsing. Nothing about the webhook dispatch endpoint or the
    event store needs to change to add one -- only a new MessagingProvider
    subclass and a registry entry.

    Deliberate limitation of this reference implementation: it verifies a
    single shared static token, not a real cryptographic signature, and it
    only parses a single JSON object (matching NormalizedMessage), not an
    array or other provider-specific shape. A real adapter's
    verify_webhook/normalize_webhook will look substantially different;
    only the generic request-context boundary (ProviderWebhookRequest) is
    the actual shared contract.
    """

    name = "simulator"

    def __init__(self, token_provider: Callable[[], str]) -> None:
        self._token_provider = token_provider

    def verify_webhook(self, request: ProviderWebhookRequest) -> bool:
        # The simulator has no cryptographic signature scheme; it reuses the
        # existing shared simulator token, read from its own header name
        # (X-WWCX-Signature). A real provider would read its own header(s)
        # here instead -- this is exactly the point of the refactor: the
        # shared route no longer knows or assumes this header name.
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
    """Build the provider name -> adapter registry used by the webhook dispatch route.

    Only the simulator is registered today. Adding a real provider is:
    implement MessagingProvider, add one entry here, and configure its
    credentials -- no changes needed elsewhere. Every adapter must preserve
    the provider-identity and inbound/outbound direction invariants documented
    on MessagingProvider.
    """
    return {"simulator": SimulatorProvider(token_provider)}
