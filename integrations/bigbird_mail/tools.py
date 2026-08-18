from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from .client import MailGatewayClient, MailGatewayError


@dataclass(frozen=True)
class MailToolConfig:
    base_url: str
    secret: str
    client_id: str

    @classmethod
    def from_environment(cls) -> "MailToolConfig":
        base_url = os.getenv("WWCX_MAIL_BASE_URL", "http://127.0.0.1:8104").strip()
        secret = os.getenv("WWCX_MAIL_GATEWAY_TOKEN", "")
        client_id = os.getenv("WWCX_MAIL_PRIVATE_AI_CLIENT_ID", "wwcx-private-ai").strip()
        if len(secret) < 32:
            raise RuntimeError("WWCX_MAIL_GATEWAY_TOKEN is required for Private AI Mail tools")
        return cls(base_url=base_url, secret=secret, client_id=client_id)


class BigBirdMailTools:
    """Least-privileged Mail Room facade for BigBird Private AI."""

    def __init__(self, config: MailToolConfig) -> None:
        self.config = config
        self.client = MailGatewayClient(
            base_url=config.base_url,
            secret=config.secret,
            client_id=config.client_id,
        )

    @staticmethod
    def _require_read_boundary(payload: dict[str, Any]) -> dict[str, Any]:
        if payload.get("mutation_authorized") is not False:
            raise MailGatewayError("mail response did not preserve non-mutation boundary")
        if payload.get("send_authorized") is not False:
            raise MailGatewayError("mail response did not preserve no-send boundary")
        return payload

    def status(self) -> dict[str, Any]:
        return self.client.status()

    def correspondence_status(self) -> dict[str, Any]:
        result = self.client.correspondence_status()
        return self._require_read_boundary(result)

    def correspondence_message(self, *, message_id: str) -> dict[str, Any]:
        result = self.client.correspondence_message(message_id)
        self._require_read_boundary(result)
        if result.get("content_is_untrusted") is not True:
            raise MailGatewayError("mail message did not preserve untrusted-content boundary")
        message = result.get("message")
        if not isinstance(message, dict):
            raise MailGatewayError("mail message response is malformed")
        provenance = message.get("provenance")
        if not isinstance(provenance, dict) or provenance.get("authoritative") is not True:
            raise MailGatewayError("mail message lacks authoritative persisted provenance")
        if provenance.get("scope") not in {"local_native", "production_native"}:
            raise MailGatewayError("mail message provenance scope is not readable")
        return result

    def correspondence_thread(self, *, thread_id: str) -> dict[str, Any]:
        result = self.client.correspondence_thread(thread_id)
        self._require_read_boundary(result)
        if result.get("content_is_untrusted") is not True:
            raise MailGatewayError("mail thread did not preserve untrusted-content boundary")
        thread = result.get("thread")
        if not isinstance(thread, dict) or not isinstance(thread.get("messages"), list):
            raise MailGatewayError("mail thread response is malformed")
        for message in thread["messages"]:
            provenance = message.get("provenance") if isinstance(message, dict) else None
            if not isinstance(provenance, dict) or provenance.get("authoritative") is not True:
                raise MailGatewayError("mail thread contains non-authoritative correspondence")
            if provenance.get("scope") not in {"local_native", "production_native"}:
                raise MailGatewayError("mail thread contains an unreadable provenance scope")
        return result

    def prepare_draft(self, request: dict[str, Any]) -> dict[str, Any]:
        result = self.client.prepare_draft(request)
        if result.get("action_token") is not None:
            raise MailGatewayError("mail draft response exposed an action token")
        preparation = result.get("preparation_api")
        if not isinstance(preparation, dict):
            raise MailGatewayError("mail draft response is malformed")
        if preparation.get("delivery_status") != "prepared_not_sent":
            raise MailGatewayError("mail draft did not remain prepared_not_sent")
        if result.get("external_delivery_enabled") is True:
            raise MailGatewayError("mail draft response unexpectedly enabled delivery")
        return result
