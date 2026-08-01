#!/usr/bin/env python3

from __future__ import annotations

import copy
import json
import pathlib
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SERVER_ROOT = ROOT / "server"
CONFIG_PATH = ROOT / "config" / "messaging" / "outbound-mail-gateway.json"

import sys

if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

import outbound_mail_preparation_auth as MODULE


class OutboundMailPreparationAuthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.gateway_config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        cls.secret = "test-preparation-secret-with-at-least-32-characters"
        cls.now = 1_800_000_000

    def active_config(self) -> dict:
        config = copy.deepcopy(self.gateway_config["preparation_api"])
        config["enabled"] = True
        return config

    def test_committed_preparation_api_is_disabled(self) -> None:
        config = self.gateway_config["preparation_api"]
        MODULE.validate_config(config)
        self.assertFalse(config["enabled"])
        status = MODULE.status_payload(config, environment={})
        self.assertFalse(status["enabled"])
        self.assertFalse(status["runtime_secret_configured"])
        self.assertNotIn(self.secret, json.dumps(status))

    def test_valid_signature_is_accepted_once(self) -> None:
        config = self.active_config()
        body = b'{"subject":"Preparation only"}'
        headers = MODULE.build_headers(
            self.secret,
            "wwcx-website-admin",
            "POST",
            "/outbound-mail/api/v1/prepare",
            body,
            timestamp=self.now,
            nonce="valid_nonce_1234567890",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            nonce_store = pathlib.Path(temp_dir) / "nonces.sqlite3"
            verified = MODULE.verify_request(
                config,
                headers,
                "POST",
                "/outbound-mail/api/v1/prepare",
                body,
                nonce_store,
                now=self.now,
                environment={config["secret_env"]: self.secret},
            )
            self.assertEqual(verified.client_id, "wwcx-website-admin")
            self.assertEqual(verified.content_sha256, MODULE.content_sha256(body))
            self.assertTrue(nonce_store.is_file())
            with self.assertRaises(MODULE.PreparationReplayError):
                MODULE.verify_request(
                    config,
                    headers,
                    "POST",
                    "/outbound-mail/api/v1/prepare",
                    body,
                    nonce_store,
                    now=self.now,
                    environment={config["secret_env"]: self.secret},
                )

    def test_tampered_body_is_rejected_before_nonce_claim(self) -> None:
        config = self.active_config()
        body = b"original"
        headers = MODULE.build_headers(
            self.secret,
            "wwcx-website-admin",
            "POST",
            "/outbound-mail/api/v1/prepare",
            body,
            timestamp=self.now,
            nonce="tamper_nonce_123456789",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            nonce_store = pathlib.Path(temp_dir) / "nonces.sqlite3"
            with self.assertRaises(MODULE.InvalidPreparationAuthError):
                MODULE.verify_request(
                    config,
                    headers,
                    "POST",
                    "/outbound-mail/api/v1/prepare",
                    b"changed",
                    nonce_store,
                    now=self.now,
                    environment={config["secret_env"]: self.secret},
                )
            self.assertFalse(nonce_store.exists())

    def test_wrong_path_or_signature_is_rejected(self) -> None:
        config = self.active_config()
        body = b"{}"
        headers = MODULE.build_headers(
            self.secret,
            "wwcx-website-admin",
            "POST",
            "/outbound-mail/api/v1/prepare",
            body,
            timestamp=self.now,
            nonce="path_nonce_123456789012",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(MODULE.InvalidPreparationAuthError):
                MODULE.verify_request(
                    config,
                    headers,
                    "POST",
                    "/outbound-mail/api/v1/other",
                    body,
                    pathlib.Path(temp_dir) / "nonces.sqlite3",
                    now=self.now,
                    environment={config["secret_env"]: self.secret},
                )

    def test_expired_timestamp_and_unknown_client_are_rejected(self) -> None:
        config = self.active_config()
        body = b""
        expired = MODULE.build_headers(
            self.secret,
            "wwcx-website-admin",
            "GET",
            "/outbound-mail/api/v1/status",
            body,
            timestamp=self.now - config["clock_skew_seconds"] - 1,
            nonce="expired_nonce_123456789",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            nonce_store = pathlib.Path(temp_dir) / "nonces.sqlite3"
            with self.assertRaises(MODULE.InvalidPreparationAuthError):
                MODULE.verify_request(
                    config,
                    expired,
                    "GET",
                    "/outbound-mail/api/v1/status",
                    body,
                    nonce_store,
                    now=self.now,
                    environment={config["secret_env"]: self.secret},
                )

            unknown = MODULE.build_headers(
                self.secret,
                "unknown-client",
                "GET",
                "/outbound-mail/api/v1/status",
                body,
                timestamp=self.now,
                nonce="unknown_nonce_123456789",
            )
            with self.assertRaises(MODULE.InvalidPreparationAuthError):
                MODULE.verify_request(
                    config,
                    unknown,
                    "GET",
                    "/outbound-mail/api/v1/status",
                    body,
                    nonce_store,
                    now=self.now,
                    environment={config["secret_env"]: self.secret},
                )

    def test_disabled_gate_and_missing_secret_are_distinct(self) -> None:
        committed = self.gateway_config["preparation_api"]
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(MODULE.PreparationApiDisabledError):
                MODULE.verify_request(
                    committed,
                    {},
                    "GET",
                    "/outbound-mail/api/v1/status",
                    b"",
                    pathlib.Path(temp_dir) / "nonces.sqlite3",
                    now=self.now,
                    environment={},
                )

        active = self.active_config()
        headers = MODULE.build_headers(
            self.secret,
            "wwcx-website-admin",
            "GET",
            "/outbound-mail/api/v1/status",
            b"",
            timestamp=self.now,
            nonce="missing_secret_123456789",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(MODULE.PreparationAuthUnavailableError):
                MODULE.verify_request(
                    active,
                    headers,
                    "GET",
                    "/outbound-mail/api/v1/status",
                    b"",
                    pathlib.Path(temp_dir) / "nonces.sqlite3",
                    now=self.now,
                    environment={},
                )


if __name__ == "__main__":
    unittest.main()
