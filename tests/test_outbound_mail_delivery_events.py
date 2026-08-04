from __future__ import annotations

import copy
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

from server import outbound_mail_delivery_events as module


class OutboundMailDeliveryEventTests(unittest.TestCase):
    def event(
        self,
        event_id: str,
        event_type: str,
        diagnostic_class: str,
        *,
        recipient: str = "a" * 64,
    ) -> dict:
        return {
            "contract": module.CONTRACT,
            "event_id": event_id,
            "event_type": event_type,
            "occurred_at": "2026-08-04T01:00:00Z",
            "provider_profile": "smtp_submission",
            "provider_message_id_sha256": "b" * 64,
            "control_id": "WWCX-PILOT-CONTROL-0001",
            "recipient_sha256": recipient,
            "source_evidence_sha256": "c" * 64,
            "source_authentication": "synthetic_test",
            "source_verified": True,
            "diagnostic_class": diagnostic_class,
            "retryable": event_type == "transient_bounce",
            "raw_recipient_stored": False,
            "raw_payload_stored": False,
            "message_content_stored": False,
        }

    def test_synthetic_event_requires_explicit_test_flag(self) -> None:
        with self.assertRaises(module.DeliveryEventValidationError):
            module.validate_event(
                self.event("event-0001", "provider_accepted", "none")
            )
        validated = module.validate_event(
            self.event("event-0001", "provider_accepted", "none"),
            allow_synthetic=True,
        )
        self.assertEqual(validated["event_type"], "provider_accepted")

    def test_raw_data_and_unverified_source_fail_closed(self) -> None:
        raw = self.event("event-0002", "delivered", "none")
        raw["raw_payload_stored"] = True
        with self.assertRaises(module.DeliveryEventValidationError):
            module.validate_event(raw, allow_synthetic=True)
        unverified = self.event("event-0003", "delivered", "none")
        unverified["source_verified"] = False
        with self.assertRaises(module.DeliveryEventValidationError):
            module.validate_event(unverified, allow_synthetic=True)

    def test_retryable_and_diagnostic_consistency(self) -> None:
        invalid = self.event("event-0004", "permanent_bounce", "mailbox_unavailable")
        invalid["retryable"] = True
        with self.assertRaises(module.DeliveryEventValidationError):
            module.validate_event(invalid, allow_synthetic=True)
        invalid = self.event("event-0005", "complaint", "unknown")
        with self.assertRaises(module.DeliveryEventValidationError):
            module.validate_event(invalid, allow_synthetic=True)

    def test_transient_failure_resets_after_delivery_without_suppression(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database = pathlib.Path(temporary) / "delivery.sqlite3"
            transient = module.apply_event(
                database,
                self.event("event-1001", "transient_bounce", "rate_limited"),
                allow_synthetic=True,
            )
            self.assertFalse(transient.suppression_active)
            self.assertEqual(transient.transient_failure_count, 1)
            delivered = module.apply_event(
                database,
                self.event("event-1002", "delivered", "none"),
                allow_synthetic=True,
            )
            self.assertFalse(delivered.suppression_active)
            self.assertEqual(delivered.transient_failure_count, 0)

    def test_permanent_bounce_suppresses_and_delivery_never_clears(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database = pathlib.Path(temporary) / "delivery.sqlite3"
            bounced = module.apply_event(
                database,
                self.event("event-2001", "permanent_bounce", "mailbox_unavailable"),
                allow_synthetic=True,
            )
            self.assertTrue(bounced.suppression_active)
            self.assertEqual(bounced.suppression_reason, "permanent_bounce")
            delivered = module.apply_event(
                database,
                self.event("event-2002", "delivered", "none"),
                allow_synthetic=True,
            )
            self.assertTrue(delivered.suppression_active)
            self.assertEqual(delivered.suppression_reason, "permanent_bounce")
            state = module.recipient_state(database, "a" * 64)
            self.assertTrue(state["suppression_active"])
            self.assertEqual(state["event_count"], 2)

    def test_complaint_and_unsubscribe_are_suppressive(self) -> None:
        for index, (event_type, diagnostic) in enumerate(
            (("complaint", "spam_complaint"), ("unsubscribe", "user_unsubscribe")),
            start=1,
        ):
            with self.subTest(event_type=event_type), tempfile.TemporaryDirectory() as temporary:
                result = module.apply_event(
                    pathlib.Path(temporary) / "delivery.sqlite3",
                    self.event(f"event-30{index:02d}", event_type, diagnostic),
                    allow_synthetic=True,
                )
                self.assertTrue(result.suppression_active)
                self.assertEqual(result.suppression_reason, event_type)

    def test_provider_rejection_does_not_suppress_recipient(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            result = module.apply_event(
                pathlib.Path(temporary) / "delivery.sqlite3",
                self.event("event-4001", "provider_rejected", "provider_unavailable"),
                allow_synthetic=True,
            )
            self.assertFalse(result.suppression_active)

    def test_duplicate_is_idempotent_and_conflict_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database = pathlib.Path(temporary) / "delivery.sqlite3"
            event = self.event("event-5001", "complaint", "spam_complaint")
            first = module.apply_event(database, event, allow_synthetic=True)
            second = module.apply_event(database, event, allow_synthetic=True)
            self.assertFalse(first.duplicate)
            self.assertTrue(second.duplicate)
            self.assertEqual(
                module.recipient_state(database, "a" * 64)["event_count"],
                1,
            )
            changed = copy.deepcopy(event)
            changed["diagnostic_class"] = "user_unsubscribe"
            changed["event_type"] = "unsubscribe"
            with self.assertRaises(module.DeliveryEventConflictError):
                module.apply_event(database, changed, allow_synthetic=True)

    def test_suppressed_recipients_returns_hashes_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database = pathlib.Path(temporary) / "delivery.sqlite3"
            suppressed_hash = "d" * 64
            module.apply_event(
                database,
                self.event(
                    "event-6001",
                    "unsubscribe",
                    "user_unsubscribe",
                    recipient=suppressed_hash,
                ),
                allow_synthetic=True,
            )
            results = module.suppressed_recipients(
                database,
                ["e" * 64, suppressed_hash],
            )
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["recipient_sha256"], suppressed_hash)
            self.assertNotIn("@", json.dumps(results))

    def test_cli_validate_apply_and_status(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        cli = root / "tools/messaging/outbound_mail_delivery_event_cli.py"
        with tempfile.TemporaryDirectory() as temporary:
            folder = pathlib.Path(temporary)
            event_path = folder / "event.json"
            database = folder / "delivery.sqlite3"
            event_path.write_text(
                json.dumps(self.event("event-7001", "complaint", "spam_complaint")),
                encoding="utf-8",
            )
            validate = subprocess.run(
                [sys.executable, str(cli), "validate", str(event_path), "--allow-synthetic"],
                cwd=root,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(validate.returncode, 0, validate.stderr)
            self.assertNotIn("@", validate.stdout)
            apply = subprocess.run(
                [
                    sys.executable,
                    str(cli),
                    "apply",
                    str(event_path),
                    "--database",
                    str(database),
                    "--allow-synthetic",
                ],
                cwd=root,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(apply.returncode, 0, apply.stderr)
            status = subprocess.run(
                [
                    sys.executable,
                    str(cli),
                    "status",
                    "a" * 64,
                    "--database",
                    str(database),
                ],
                cwd=root,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(status.returncode, 0, status.stderr)
            state = json.loads(status.stdout)
            self.assertTrue(state["suppression_active"])
            self.assertEqual(state["suppression_reason"], "complaint")


if __name__ == "__main__":
    unittest.main()
