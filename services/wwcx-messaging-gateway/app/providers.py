from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable

from .models import NormalizedMessage


@dataclass(frozen=True)
class SendResult:
    provider_message_id: str
    accepted: bool


class MessagingProvider(ABC):
    """Boundary implemented by Telnyx, Bandwidth, and simulator adapters."""

    name: str

    @abstractmethod
    def verify_webhook(
        self,
        body: bytes,
        signature: str | None,
        timestamp: str | None,
    ) -> bool:
        """Return True only for authentic, timely provider callbacks."""
        raise NotImplementedError

    @abstractmethod
    def normalize_webhook(self, payload: dict[str, object]) -> NormalizedMessage:
        """Convert provider-specific payloads into the WW.CX message model."""
        raise NotImplementedError

    @abstractmethod
    def send(self, message: NormalizedMessage) -> SendResult:
        """Submit an outbound message and return the provider identifier."""
        raise NotImplementedError


class SimulatorProvider(MessagingProvider):
    """Reference MessagingProvider implementation used for local/dev testing.

    This is the first concrete implementation of the abstraction above --
    previously the ABC existed but nothing used it; the simulator intake
    endpoint (/v1/simulator/messages) accepted NormalizedMessage bodies
    directly, bypassing verify_webhook/normalize_webhook entirely.

    A real carrier adapter (Telnyx, Bandwidth, etc.) implements this same
    interface with actual HMAC/webhook signature verification and
    provider-specific payload parsing. Nothing about the webhook dispatch
    endpoint or the event store needs to change to add one -- only a new
    MessagingProvider subclass and a registry entry.
    """

    name = "simulator"

    def __init__(self, token_provider: Callable[[], str]) -> None:
        self._token_provider = token_provider

    def verify_webhook(
        self,
        body: bytes,
        signature: str | None,
        timestamp: str | None,
    ) -> bool:
        # The simulator has no cryptographic signature scheme; it reuses the
        # existing shared simulator token as the "signature" for consistency
        # with the rest of the simulator surface (WWCX_SIMULATOR_TOKEN).
        del body, timestamp
        return signature == self._token_provider()

    def normalize_webhook(self, payload: dict[str, object]) -> NormalizedMessage:
        return NormalizedMessage.model_validate(payload)

    def send(self, message: NormalizedMessage) -> SendResult:
        return SendResult(provider_message_id=f"sim-{message.event_id}", accepted=True)


def build_provider_registry(token_provider: Callable[[], str]) -> dict[str, MessagingProvider]:
    """Build the provider name -> adapter registry used by the webhook dispatch route.

    Only the simulator is registered today. Adding a real provider is:
    implement MessagingProvider, add one entry here, and configure its
    credentials -- no changes needed elsewhere.
    """
    return {"simulator": SimulatorProvider(token_provider)}
