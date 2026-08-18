#!/usr/bin/env python3
"""Tests for explicit, fail-closed Mail Room thread correlation metadata."""

from __future__ import annotations

import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVER = ROOT / "server"
if str(SERVER) not in sys.path:
    sys.path.insert(0, str(SERVER))

import mail_threading  # noqa: E402


def test_explicit_reply_context_builds_headers() -> None:
    preview = {"request": {}, "headers": {}}
    payload = {
        "correspondence_id": "CORR-0001",
        "thread_id": "THREAD-0001",
        "source_message_id": "<incoming-1@example.net>",
        "references": ["<older-1@example.net>"],
        "provider_thread_id": "provider-thread-123",
        "provider_message_id": "provider-message-456",
    }

    result = mail_threading.apply_to_preview(preview, payload)
    context = result["threading"]

    assert context["contract"] == "wwcx.mail-threading.v1"
    assert context["correlation_strength"] == "explicit"
    assert context["fallback_correlation_used"] is False
    assert context["in_reply_to"] == "<incoming-1@example.net>"
    assert context["references"] == [
        "<older-1@example.net>",
        "<incoming-1@example.net>",
    ]
    assert result["headers"]["X-WWCX-Correspondence-ID"] == "CORR-0001"
    assert result["headers"]["X-WWCX-Thread-ID"] == "THREAD-0001"
    assert result["headers"]["In-Reply-To"] == "<incoming-1@example.net>"
    assert result["headers"]["References"] == (
        "<older-1@example.net> <incoming-1@example.net>"
    )
    assert "provider-thread-123" not in result["headers"].values()
    assert "provider-message-456" not in result["headers"].values()


def test_no_evidence_does_not_guess() -> None:
    context = mail_threading.normalize_thread_context({})
    assert context["correlation_strength"] == "none"
    assert context["fallback_correlation_used"] is False
    assert context["in_reply_to"] is None
    assert context["references"] == []


def test_header_injection_is_rejected() -> None:
    try:
        mail_threading.normalize_thread_context(
            {"provider_thread_id": "safe\r\nBcc: attacker@example.net"}
        )
    except mail_threading.ThreadingError as exc:
        assert "provider_thread_id is invalid" in str(exc)
    else:
        raise AssertionError("header injection metadata must be rejected")


def test_noncanonical_message_id_is_rejected() -> None:
    try:
        mail_threading.normalize_thread_context({"in_reply_to": "not-a-message-id"})
    except mail_threading.ThreadingError as exc:
        assert "canonical RFC-style Message-ID" in str(exc)
    else:
        raise AssertionError("malformed Message-ID must be rejected")
