from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from .client import MessagingGatewayClient, MessagingGatewayError


@dataclass(frozen=True)
class MessagingToolConfig:
    base_url: str
    read_token: str
    control_token: str | None
    control_enabled: bool

    @classmethod
    def from_environment(cls) -> "MessagingToolConfig":
        base_url = os.getenv("WWCX_MESSAGING_BASE_URL", "").strip()
        read_token = os.getenv("WWCX_MESSAGING_READ_TOKEN", "").strip()
        control_token = os.getenv("WWCX_MESSAGING_CONTROL_TOKEN", "").strip() or None
        control_enabled = os.getenv("WWCX_MESSAGING_CONTROL_ENABLED", "false").lower() == "true"
        if not base_url:
            raise RuntimeError("WWCX_MESSAGING_BASE_URL is required")
        if not read_token:
            raise RuntimeError("WWCX_MESSAGING_READ_TOKEN is required")
        if control_enabled and not control_token:
            raise RuntimeError("control is enabled but WWCX_MESSAGING_CONTROL_TOKEN is missing")
        return cls(base_url, read_token, control_token, control_enabled)


class BigBirdMessagingTools:
    """Least-privileged BigBird tool facade for WW.CX messaging management."""

    def __init__(self, config: MessagingToolConfig) -> None:
        self.config = config
        self.client = MessagingGatewayClient(
            base_url=config.base_url,
            read_token=config.read_token,
            control_token=config.control_token,
        )

    def status(self) -> dict[str, Any]:
        return self.client.status()

    def pause(self, *, actor: str, reason: str) -> dict[str, Any]:
        self._require_control_enabled()
        return self.client.pause(actor=actor, reason=reason)

    def resume(self, *, actor: str, reason: str) -> dict[str, Any]:
        self._require_control_enabled()
        return self.client.resume(actor=actor, reason=reason)

    def _require_control_enabled(self) -> None:
        if not self.config.control_enabled:
            raise MessagingGatewayError("messaging control tools are disabled")
