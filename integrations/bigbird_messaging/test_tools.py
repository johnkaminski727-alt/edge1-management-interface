from __future__ import annotations

import pytest

from integrations.bigbird_messaging.client import MessagingGatewayError
from integrations.bigbird_messaging.tools import BigBirdMessagingTools, MessagingToolConfig


def test_environment_requires_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("WWCX_MESSAGING_BASE_URL", raising=False)
    monkeypatch.setenv("WWCX_MESSAGING_READ_TOKEN", "read")
    with pytest.raises(RuntimeError, match="BASE_URL"):
        MessagingToolConfig.from_environment()


def test_environment_requires_read_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WWCX_MESSAGING_BASE_URL", "http://127.0.0.1:8080")
    monkeypatch.delenv("WWCX_MESSAGING_READ_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="READ_TOKEN"):
        MessagingToolConfig.from_environment()


def test_control_enabled_requires_control_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WWCX_MESSAGING_BASE_URL", "http://127.0.0.1:8080")
    monkeypatch.setenv("WWCX_MESSAGING_READ_TOKEN", "read")
    monkeypatch.setenv("WWCX_MESSAGING_CONTROL_ENABLED", "true")
    monkeypatch.delenv("WWCX_MESSAGING_CONTROL_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="CONTROL_TOKEN"):
        MessagingToolConfig.from_environment()


def test_control_is_disabled_by_default() -> None:
    tools = BigBirdMessagingTools(
        MessagingToolConfig(
            base_url="http://127.0.0.1:8080",
            read_token="read",
            control_token="control",
            control_enabled=False,
        )
    )
    with pytest.raises(MessagingGatewayError, match="disabled"):
        tools.pause(actor="operator", reason="maintenance")
