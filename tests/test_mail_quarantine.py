#!/usr/bin/env python3
"""Tests for sanitized Mail Room quarantine metadata and release gates."""

from __future__ import annotations

import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVER_ROOT = ROOT / "server"
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

import mail_quarantine as MODULE


class MailQuarantineTests(unittest.TestCase):
    def record_data(self) -> dict:
        return {
            "quarantine_id": "QUAR-0001",
            "correspondence_id": "CORR-0001",
            "message_sha256": "a" * 64,
            "original_recipient_sha256": "b" * 64,
            "created_at": "2026-08-18T05:00:00+00:00",
            "route_decision": "security_quarantine",
            "reason_codes": ["scan:clamav:infected"],
            "security_signals": ["malware_detected"],
            "scan_evidence": [
                {
                    "engine": "clamav",
                    "engine_version": "1.0",
                    "ruleset_version": "db-1",
                    "state": "infected",
                }
            ],
            "provenance": {
                "source": "trusted_local_adapter",
                "source_event_sha256": "c" * 64,
                "decision_contract": "wwcx.mail-threat-decision.v1",
            },
        }

    def test_record_is_sanitized_and_nonreleasing(self) -> None:
        record = MODULE.build_record(self.record_data())
        self.assertEqual(record["disposition"], "quarantine")
        self.assertFalse(record["message_body_stored"])
        self.assertFalse(record["attachment_bytes_stored"])
        self.assertFalse(record["active_content_executed"])
        self.assertFalse(record["automatic_release_allowed"])
        self.assertFalse(record["ai_release_allowed"])

    def test_raw_or_unexpected_fields_are_rejected(self) -> None:
        data = self.record_data()
        data["raw_message"] = "must not be stored"
        with self.assertRaisesRegex(MODULE.QuarantineError, "keys are invalid"):
            MODULE.build_record(data)

    def test_ai_release_request_has_no_authority(self) -> None:
        result = MODULE.evaluate_release(
            {
                "operator_approved": True,
                "security_rescan_clean": True,
                "destination_validated": True,
                "policy_authorized": True,
                "ai_requested_release": True,
            }
        )
        self.assertFalse(result["eligible_for_operator_release"])
        self.assertFalse(result["ai_has_release_authority"])
        self.assertIn("ai_release_request_has_no_authority", result["block_reasons"])

    def test_every_authoritative_release_gate_is_required(self) -> None:
        baseline = {
            "operator_approved": True,
            "security_rescan_clean": True,
            "destination_validated": True,
            "policy_authorized": True,
            "ai_requested_release": False,
        }
        self.assertTrue(MODULE.evaluate_release(baseline)["eligible_for_operator_release"])
        for gate in (
            "operator_approved",
            "security_rescan_clean",
            "destination_validated",
            "policy_authorized",
        ):
            with self.subTest(gate=gate):
                candidate = dict(baseline)
                candidate[gate] = False
                result = MODULE.evaluate_release(candidate)
                self.assertFalse(result["eligible_for_operator_release"])
                self.assertFalse(result["automatic_release_attempted"])


if __name__ == "__main__":
    unittest.main()
