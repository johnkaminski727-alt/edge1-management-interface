#!/usr/bin/env python3
"""Tests for explicit, fail-closed Mail Room thread correlation metadata."""

from __future__ import annotations

import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVER = ROOT / "server"
if str(SERVER) not in sys.path:
    sys.path.insert(0, str(SERVER))

import mail_threading  # noqa: E402


class MailThreadingTests(unittest.TestCase):
    def test_explicit_reply_context_builds_headers(self) -> None:
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

        self.assertEqual(context["contract"], "wwcx.mail-threading.v1")
        self.assertEqual(context["correlation_strength"], "explicit")
        self.assertFalse(context["fallback_correlation_used"])
        self.assertEqual(context["in_reply_to"], "<incoming-1@example.net>")
        self.assertEqual(
            context["references"],
            ["<older-1@example.net>", "<incoming-1@example.net>"],
        )
        self.assertEqual(result["headers"]["X-WWCX-Correspondence-ID"], "CORR-0001")
        self.assertEqual(result["headers"]["X-WWCX-Thread-ID"], "THREAD-0001")
        self.assertEqual(result["headers"]["In-Reply-To"], "<incoming-1@example.net>")
        self.assertEqual(
            result["headers"]["References"],
            "<older-1@example.net> <incoming-1@example.net>",
        )
        self.assertNotIn("provider-thread-123", result["headers"].values())
        self.assertNotIn("provider-message-456", result["headers"].values())

    def test_no_evidence_does_not_guess(self) -> None:
        context = mail_threading.normalize_thread_context({})
        self.assertEqual(context["correlation_strength"], "none")
        self.assertFalse(context["fallback_correlation_used"])
        self.assertIsNone(context["in_reply_to"])
        self.assertEqual(context["references"], [])

    def test_header_injection_is_rejected(self) -> None:
        with self.assertRaisesRegex(mail_threading.ThreadingError, "provider_thread_id is invalid"):
            mail_threading.normalize_thread_context(
                {"provider_thread_id": "safe\r\nBcc: attacker@example.net"}
            )

    def test_noncanonical_message_id_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            mail_threading.ThreadingError,
            "canonical RFC-style Message-ID",
        ):
            mail_threading.normalize_thread_context({"in_reply_to": "not-a-message-id"})


if __name__ == "__main__":
    unittest.main()
