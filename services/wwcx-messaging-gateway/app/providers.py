from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

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
