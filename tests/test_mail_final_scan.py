#!/usr/bin/env python3
"""Tests for the provider-neutral final outbound MIME scan contract."""

from __future__ import annotations

import hashlib
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVER_ROOT = ROOT / "server"
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

import mail_final_scan as MODULE


class MailFinalScanTests(unittest.TestCase):
    def clean_result(self, message_bytes: bytes) -> dict:
        return {
            "contract": "wwcx.mail-final-scan.v1",
            "state": "clean",
            "engine": "synthetic-test-scanner",
            "engine_version": "1.0",
            "ruleset_version": "test-rules-1",
            "message_sha256": hashlib.sha256(message_bytes).hexdigest(),
            "reason_codes": [],
        }

    def test_clean_exact_digest_is_accepted(self) -> None:
        message = b"From: sender@example.com\r\n\r\nbody\r\n"
        result = MODULE.require_clean(message, self.clean_result)
        self.assertEqual(result["state"], "clean")
        self.assertEqual(result["message_sha256"], hashlib.sha256(message).hexdigest())

    def test_missing_scanner_fails_closed(self) -> None:
        with self.assertRaisesRegex(MODULE.FinalScanError, "not configured"):
            MODULE.require_clean(b"message", None)

    def test_digest_mismatch_fails_closed(self) -> None:
        def scanner(message_bytes: bytes) -> dict:
            result = self.clean_result(message_bytes)
            result["message_sha256"] = "0" * 64
            return result

        with self.assertRaisesRegex(MODULE.FinalScanError, "digest"):
            MODULE.require_clean(b"message", scanner)

    def test_every_nonclean_normalized_state_fails_closed(self) -> None:
        for state in (
            "infected",
            "suspicious",
            "unscannable",
            "scan_error",
            "not_scanned",
        ):
            with self.subTest(state=state):
                def scanner(message_bytes: bytes, scan_state: str = state) -> dict:
                    result = self.clean_result(message_bytes)
                    result["state"] = scan_state
                    result["reason_codes"] = [f"synthetic_{scan_state}"]
                    return result

                with self.assertRaisesRegex(MODULE.FinalScanError, "not clean"):
                    MODULE.require_clean(b"message", scanner)

    def test_unbounded_or_injected_metadata_is_rejected(self) -> None:
        message = b"message"
        result = self.clean_result(message)
        result["engine"] = "scanner\r\nX-Evil: yes"
        with self.assertRaises(MODULE.FinalScanError):
            MODULE.normalize_result(result, message)


if __name__ == "__main__":
    unittest.main()
