from __future__ import annotations

import pytest

from integrations.bigbird_messaging.client import MessagingGatewayError
from integrations.bigbird_messaging.tools import BigBirdMessagingTools, MessagingToolConfig


class FakeClient:
    def recent_messages(self, *, limit: int = 25):
        return {
            "events": [],
            "limit": limit,
            "content_is_untrusted": True,
            "mutation_authorized": False,
        }

    def message(self, event_id: str):
        return {"event": {"event_id": event_id}, "mutation_authorized": False}


class UnsafeFakeClient(FakeClient):
    def recent_messages(self, *, limit: int = 25):
        return {"events": [], "mutation_authorized": True}


def tools() -> BigBirdMessagingTools:
    value = BigBirdMessagingTools(
        MessagingToolConfig(
            base_url="http://127.0.0.1:8080",
            read_token="read",
            control_token=None,
            control_enabled=False,
        )
    )
    value.client = FakeClient()
    return value


def test_recent_conversations_preserve_read_only_boundary() -> None:
    result = tools().recent_conversations(limit=7)
    assert result["limit"] == 7
    assert result["mutation_authorized"] is False


def test_read_tool_fails_closed_on_unsafe_response() -> None:
    value = tools()
    value.client = UnsafeFakeClient()
    with pytest.raises(MessagingGatewayError, match="read-only boundary"):
        value.recent_conversations()


def test_prepare_reply_is_local_draft_not_send() -> None:
    result = tools().prepare_reply(event_id="evt-1", text="Proposed response")
    assert result["contract"] == "wwcx.messages-draft.v1"
    assert result["state"] == "drafted"
    assert result["delivery_status"] == "prepared_not_sent"
    assert result["send_authorized"] is False
    assert result["mutation_authorized"] is False


def test_prepare_reply_rejects_empty_or_oversized_text() -> None:
    value = tools()
    with pytest.raises(ValueError):
        value.prepare_reply(event_id="evt-1", text="   ")
    with pytest.raises(ValueError):
        value.prepare_reply(event_id="evt-1", text="x" * 4001)
