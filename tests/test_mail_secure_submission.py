#!/usr/bin/env python3
"""Tests for the final-scan provider submission boundary."""

from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import sys
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVER_ROOT = ROOT / "server"
CONFIG_PATH = ROOT / "config" / "messaging" / "outbound-mail-gateway.json"
POLICY_PATH = ROOT / "config" / "messaging" / "outbound-mail-policy.json"
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

import mail_secure_submission as MODULE
import outbound_mail_gateway
import outbound_mail_policy


class MailSecureSubmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        cls.policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))

    def active_config(self) -> dict:
        config = copy.deepcopy(self.config)
        config["enabled"] = True
        config["deployment_authorized"] = True
        config["external_delivery_authorized"] = True
        config["admin"]["send_endpoint_enabled"] = True
        config["provider"]["selected"] = "smtp_submission"
        config["provider"]["profiles"]["smtp_submission"]["enabled"] = True
        outbound_mail_gateway.validate_gateway_config(config)
        return config

    def active_policy(self) -> dict:
        return outbound_mail_policy.activated_copy(
            self.policy,
            "151 2 Street South, Invermay, SK",
        )

    def preview(self, config: dict, policy: dict) -> dict:
        return outbound_mail_gateway.compose_preview(
            config,
            policy,
            {
                "from_address": "john@ww.cx",
                "to": "recipient@example.com",
                "subject": "Secure submission test",
                "body": "Synthetic repository test only.",
                "message_class": "business_correspondence",
                "mailing_address": "151 2 Street South, Invermay, SK",
            },
        )

    @staticmethod
    def clean_result(message_bytes: bytes) -> dict:
        return {
            "contract": "wwcx.mail-final-scan.v1",
            "state": "clean",
            "engine": "synthetic-test-scanner",
            "engine_version": "1.0",
            "ruleset_version": "test-rules-1",
            "message_sha256": hashlib.sha256(message_bytes).hexdigest(),
            "reason_codes": [],
        }

    def test_missing_scanner_blocks_before_provider_submission(self) -> None:
        config = self.active_config()
        policy = self.active_policy()
        preview = self.preview(config, policy)
        with mock.patch.object(MODULE, "_submit_smtp_message") as submit:
            with self.assertRaisesRegex(
                outbound_mail_gateway.DeliveryDisabledError,
                "scanner is not configured",
            ):
                MODULE.send_preview(
                    config,
                    policy,
                    preview,
                    confirmation=True,
                    final_scanner=None,
                )
        submit.assert_not_called()

    def test_nonclean_scan_blocks_before_provider_submission(self) -> None:
        config = self.active_config()
        policy = self.active_policy()
        preview = self.preview(config, policy)

        def scanner(message_bytes: bytes) -> dict:
            result = self.clean_result(message_bytes)
            result["state"] = "suspicious"
            result["reason_codes"] = ["synthetic_suspicious"]
            return result

        with mock.patch.object(MODULE, "_submit_smtp_message") as submit:
            with self.assertRaisesRegex(
                outbound_mail_gateway.DeliveryDisabledError,
                "not clean: suspicious",
            ):
                MODULE.send_preview(
                    config,
                    policy,
                    preview,
                    confirmation=True,
                    final_scanner=scanner,
                )
        submit.assert_not_called()

    def test_clean_scan_covers_exact_provider_bytes(self) -> None:
        config = self.active_config()
        policy = self.active_policy()
        preview = self.preview(config, policy)
        scanned: list[bytes] = []

        def scanner(message_bytes: bytes) -> dict:
            scanned.append(message_bytes)
            return self.clean_result(message_bytes)

        delivery = {
            "provider": "smtp_submission",
            "provider_type": "smtp",
            "message_id": "<synthetic@ww.cx>",
            "recipient_count": 1,
            "submitted_at": "2026-08-18T00:00:00+00:00",
        }
        with mock.patch.object(
            MODULE,
            "_submit_smtp_message",
            return_value=delivery,
        ) as submit:
            result = MODULE.send_preview(
                config,
                policy,
                preview,
                confirmation=True,
                final_scanner=scanner,
            )

        provider_bytes = submit.call_args.args[2]
        self.assertEqual(len(scanned), 1)
        self.assertEqual(scanned[0], provider_bytes)
        self.assertEqual(
            result["final_scan"]["message_sha256"],
            hashlib.sha256(provider_bytes).hexdigest(),
        )
        self.assertEqual(result["audit_event"]["final_scan"]["state"], "clean")


if __name__ == "__main__":
    unittest.main()
