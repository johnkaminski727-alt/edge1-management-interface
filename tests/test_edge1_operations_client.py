from __future__ import annotations

import hashlib
import hmac
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

from server.edge1_operations_client import (
    Edge1OperationsClient,
    OperationsClientError,
    OperationsClientTimeout,
)


class FakeResponse:
    def __init__(self, payload: dict, status: int = 200):
        self.payload = json.dumps(payload).encode("utf-8")
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self, limit: int) -> bytes:
        return self.payload[:limit]


class OperationsClientTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.secret_path = Path(self.temp.name) / "operations.secret"
        self.secret = b"s" * 48
        self.secret_path.write_bytes(self.secret)
        os.chmod(self.secret_path, 0o600)

    def tearDown(self):
        self.temp.cleanup()

    def client(self) -> Edge1OperationsClient:
        return Edge1OperationsClient(
            secret_path=self.secret_path,
            timeout_seconds=7,
            now=lambda: 1800000000,
        )

    def test_exact_hmac_request_and_normalized_success(self):
        captured = {}

        def fake_urlopen(request, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return FakeResponse({
                "event_id": "ops-event-123",
                "action": "security.validate_config",
                "status": "succeeded",
                "exit_code": 0,
                "duration_ms": 19,
                "stdout": "must not escape the client result",
                "stderr": "must not escape the client result",
            })

        with patch("server.edge1_operations_client.secrets.token_hex", return_value="a" * 48), \
             patch("server.edge1_operations_client.urlopen", side_effect=fake_urlopen):
            result = self.client().run("security.validate_config", "wwcx-user-42")

        request = captured["request"]
        self.assertEqual(request.full_url, "http://127.0.0.1:8097/v1/actions/security.validate_config/run")
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.data, b"{}")
        self.assertEqual(captured["timeout"], 7)
        headers = {key.lower(): value for key, value in request.header_items()}
        actor = "edge1-security-console:wwcx-user-42"
        body_hash = hashlib.sha256(b"{}").hexdigest()
        canonical = "\n".join((
            "POST",
            "/v1/actions/security.validate_config/run",
            "1800000000",
            "a" * 48,
            actor,
            body_hash,
        )).encode("utf-8")
        expected = hmac.new(self.secret, canonical, hashlib.sha256).hexdigest()
        self.assertEqual(headers["x-wwcx-actor"], actor)
        self.assertEqual(headers["x-wwcx-nonce"], "a" * 48)
        self.assertEqual(headers["x-wwcx-timestamp"], "1800000000")
        self.assertEqual(headers["x-wwcx-signature"], expected)
        self.assertEqual(result.event_id, "ops-event-123")
        self.assertEqual(result.status, "succeeded")
        self.assertEqual(result.message, "The security configuration passed validation.")
        self.assertFalse(hasattr(result, "stdout"))
        self.assertFalse(hasattr(result, "stderr"))

    def test_unknown_action_and_broad_secret_permissions_fail_closed(self):
        with self.assertRaises(OperationsClientError):
            self.client().run("security.rules.reload", "wwcx-user-42")
        os.chmod(self.secret_path, 0o640)
        with self.assertRaises(OperationsClientError):
            self.client().run("security.validate_config", "wwcx-user-42")

    def test_timeout_and_unreadable_response_are_normalized(self):
        with patch("server.edge1_operations_client.urlopen", side_effect=URLError(TimeoutError())):
            with self.assertRaises(OperationsClientTimeout):
                self.client().run("security.validate_config", "wwcx-user-42")
        with patch("server.edge1_operations_client.urlopen", return_value=FakeResponse({"status": "succeeded"})):
            with self.assertRaises(OperationsClientError):
                self.client().run("security.validate_config", "wwcx-user-42")


if __name__ == "__main__":
    unittest.main()
