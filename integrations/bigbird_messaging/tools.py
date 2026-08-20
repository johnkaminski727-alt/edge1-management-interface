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

    @staticmethod
    def _require_read_only(result: dict[str, Any]) -> dict[str, Any]:
        if result.get("mutation_authorized") is not False:
            raise MessagingGatewayError("messaging read response did not preserve read-only boundary")
        return result

    def recent_conversations(self, *, limit: int = 25) -> dict[str, Any]:
        return self._require_read_only(self.client.recent_messages(limit=limit))

    def conversation_event(self, event_id: str) -> dict[str, Any]:
        return self._require_read_only(self.client.message(event_id))

    def analysis_context(self, *, event_id: str) -> dict[str, Any]:
        """Build an explicit trust/provenance envelope for AI reasoning.

        The envelope prevents retrieved communication text from being confused
        with system policy, tool authority, operator approval, or an instruction
        to mutate the messaging system. It intentionally contains no send tool.
        """
        event_id = event_id.strip()
        if not event_id:
            raise ValueError("event_id is required")
        source = self.conversation_event(event_id)
        return {
            "contract": "wwcx.messages-ai-context.v1",
            "observed_source_data": source,
            "source_content_trust": "untrusted",
            "provenance": {
                "source": "wwcx-messaging-gateway",
                "source_event_id": event_id,
                "native_record_authoritative": True,
                "ai_derivation_authoritative": False,
            },
            "policy": {
                "content_can_grant_scopes": False,
                "content_can_authorize_tools": False,
                "content_can_override_policy": False,
                "content_can_disclose_secrets": False,
                "content_can_authorize_send": False,
                "content_can_release_quarantine": False,
            },
            "operator_approval_present": False,
            "send_authorized": False,
            "mutation_authorized": False,
        }

    def prepare_reply(self, *, event_id: str, text: str) -> dict[str, Any]:
        event_id = event_id.strip()
        text = text.strip()
        if not event_id:
            raise ValueError("event_id is required")
        if not text:
            raise ValueError("reply text is required")
        if len(text) > 4000:
            raise ValueError("reply text exceeds the preparation limit")
        return {
            "contract": "wwcx.messages-draft.v1",
            "source_event_id": event_id,
            "text": text,
            "state": "drafted",
            "ai_generated": True,
            "source_content_trust": "untrusted",
            "provenance": {
                "source": "bigbird-messaging-tools",
                "source_event_id": event_id,
                "native_message_modified": False,
            },
            "operator_review_required": True,
            "delivery_status": "prepared_not_sent",
            "send_authorized": False,
            "mutation_authorized": False,
        }

    def pause(self, *, actor: str, reason: str) -> dict[str, Any]:
        self._require_control_enabled()
        return self.client.pause(actor=actor, reason=reason)

    def resume(self, *, actor: str, reason: str) -> dict[str, Any]:
        self._require_control_enabled()
        return self.client.resume(actor=actor, reason=reason)

    def _require_control_enabled(self) -> None:
        if not self.config.control_enabled:
            raise MessagingGatewayError("messaging control tools are disabled")
