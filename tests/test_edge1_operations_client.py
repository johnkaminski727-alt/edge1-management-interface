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

    def test_root_owned_systemd_credential_mode_0440_is_accepted(self):
        from types import SimpleNamespace

        client = Edge1OperationsClient(
            secret_path=Path("/run/credentials/edge1-security-auth.service/operations_api_secret")
        )

        with patch.object(Path, "is_symlink", return_value=False), \
             patch.object(Path, "stat", return_value=SimpleNamespace(st_mode=0o100440, st_uid=0, st_gid=0)), \
             patch.object(Path, "read_bytes", return_value=b"s" * 64):
            self.assertEqual(client._read_secret(), b"s" * 64)

    def test_systemd_credential_rejects_non_root_ownership(self):
        from types import SimpleNamespace

        client = Edge1OperationsClient(
            secret_path=Path("/run/credentials/edge1-security-auth.service/operations_api_secret")
        )

        with patch.object(Path, "is_symlink", return_value=False), \
             patch.object(Path, "stat", return_value=SimpleNamespace(st_mode=0o100440, st_uid=33, st_gid=33)), \
             patch.object(Path, "read_bytes", return_value=b"s" * 64):
            with self.assertRaises(OperationsClientError):
                client._read_secret()


if __name__ == "__main__":
    unittest.main()


class ContactsTypedActionClientTests(unittest.TestCase):
    def _secret(self):
        import tempfile
        from pathlib import Path

        directory = tempfile.TemporaryDirectory()
        path = Path(directory.name) / "secret"
        path.write_bytes(b"x" * 64)
        path.chmod(0o600)
        return directory, path

    def test_contacts_action_serializes_parameters_and_signs_exact_body(self):
        import hashlib
        import hmac
        import json
        from unittest.mock import patch

        from server.edge1_operations_client import Edge1OperationsClient

        directory, secret = self._secret()
        captured = {}

        class Response:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self, _limit):
                return json.dumps({
                    "event_id": "contacts-event-1",
                    "status": "succeeded",
                }).encode()

        def fake_urlopen(request, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return Response()

        client = Edge1OperationsClient(
            secret_path=secret,
            now=lambda: 1234567890,
        )

        parameters = {
            "candidate_id": 7,
            "provenance_id": 11,
            "evidence_role": "supporting",
        }

        with patch(
            "server.edge1_operations_client.secrets.token_hex",
            return_value="a" * 48,
        ), patch(
            "server.edge1_operations_client.urlopen",
            side_effect=fake_urlopen,
        ):
            result = client.run(
                "contacts.correlation.promote",
                "john",
                parameters=parameters,
            )

        request = captured["request"]

        expected_body = json.dumps(
            parameters,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode()

        self.assertEqual(request.data, expected_body)
        self.assertEqual(
            request.full_url,
            "http://127.0.0.1:8097/"
            "v1/actions/contacts.correlation.promote/run",
        )

        actor = "edge1-security-console:john"
        body_hash = hashlib.sha256(expected_body).hexdigest()

        canonical = "\n".join((
            "POST",
            "/v1/actions/contacts.correlation.promote/run",
            "1234567890",
            "a" * 48,
            actor,
            body_hash,
        )).encode()

        expected_signature = hmac.new(
            b"x" * 64,
            canonical,
            hashlib.sha256,
        ).hexdigest()

        self.assertEqual(
            request.headers["X-wwcx-signature"],
            expected_signature,
        )
        self.assertEqual(result.action_id, "contacts.correlation.promote")
        self.assertEqual(result.status, "succeeded")

        directory.cleanup()

    def test_contacts_accept_and_reject_are_allowlisted(self):
        from server.edge1_operations_client import ACTION_PATHS

        self.assertEqual(
            ACTION_PATHS["contacts.correlation.accept"],
            "/v1/actions/contacts.correlation.accept/run",
        )
        self.assertEqual(
            ACTION_PATHS["contacts.correlation.reject"],
            "/v1/actions/contacts.correlation.reject/run",
        )

    def test_unknown_action_remains_rejected(self):
        from server.edge1_operations_client import (
            Edge1OperationsClient,
            OperationsClientError,
        )

        directory, secret = self._secret()

        client = Edge1OperationsClient(secret_path=secret)

        with self.assertRaises(OperationsClientError):
            client.run(
                "contacts.correlation.merge",
                "john",
                parameters={"candidate_id": 1},
            )

        directory.cleanup()

    def test_non_object_parameters_are_rejected(self):
        from server.edge1_operations_client import (
            Edge1OperationsClient,
            OperationsClientError,
        )

        directory, secret = self._secret()

        client = Edge1OperationsClient(secret_path=secret)

        with self.assertRaises(OperationsClientError):
            client.run(
                "contacts.correlation.accept",
                "john",
                parameters=["bad"],
            )

        directory.cleanup()
