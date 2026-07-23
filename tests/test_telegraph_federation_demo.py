#!/usr/bin/env python3
"""Tests for the non-production Telegraph Federation reference fixture."""

from __future__ import annotations

import time
import unittest

from reference.telegraph_federation_demo import Office, ReplayCache, run_demo


class TelegraphFederationDemoTests(unittest.TestCase):
    def test_end_to_end_demo_checks_pass(self) -> None:
        result = run_demo()
        self.assertTrue(result["checks"])
        self.assertTrue(all(result["checks"].values()))
        self.assertEqual(result["route_decision"]["result"], "selected")
        self.assertEqual(result["receipts"][0]["event"], "delivered_to_endpoint")
        self.assertEqual(result["receipts"][1]["event"], "duplicate_rejected")

    def test_route_rejects_missing_accessibility_media(self) -> None:
        alpha = Office(
            "alpha.telegraph.ww.cx",
            {"secure_message", "rtt_t140"},
            {"end_to_end_encryption", "signed_receipts"},
            {"legacy.telegraph.example": "trusted"},
        )
        legacy = Office(
            "legacy.telegraph.example",
            {"secure_message"},
            {"end_to_end_encryption", "signed_receipts"},
            {"alpha.telegraph.ww.cx": "trusted"},
        )

        decision = alpha.route(
            legacy,
            {
                "message_id": "0123456789abcdef0123456789abcdef",
                "security": {"end_to_end_encryption", "signed_receipts"},
                "media": {"secure_message", "rtt_t140"},
            },
        )

        self.assertEqual(decision["result"], "rejected")
        self.assertIn("media_mismatch", decision["reason_codes"])
        self.assertFalse(decision["selected_path"]["eligible"])

    def test_route_rejects_untrusted_peer(self) -> None:
        alpha = Office(
            "alpha.telegraph.ww.cx",
            {"secure_message"},
            {"end_to_end_encryption"},
            {},
        )
        unknown = Office(
            "unknown.telegraph.example",
            {"secure_message"},
            {"end_to_end_encryption"},
            {},
        )

        decision = alpha.route(
            unknown,
            {
                "message_id": "abcdef0123456789abcdef0123456789",
                "security": {"end_to_end_encryption"},
                "media": {"secure_message"},
            },
        )

        self.assertEqual(decision["result"], "rejected")
        self.assertIn("insufficient_trust", decision["reason_codes"])

    def test_replay_cache_expires_old_nonce(self) -> None:
        cache = ReplayCache()
        now = time.time()
        self.assertTrue(cache.accept("nonce-0123456789", now, 60))
        self.assertFalse(cache.accept("nonce-0123456789", now + 1, 60))
        self.assertTrue(cache.accept("nonce-0123456789", now + 61, 60))


if __name__ == "__main__":
    unittest.main()
