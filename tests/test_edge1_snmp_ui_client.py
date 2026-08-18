from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from server.edge1_snmp_ui_client import Edge1SnmpUiClient, SnmpUiClientError, sanitize_for_browser


class Response:
    status = 200
    def __init__(self, payload): self.payload = payload
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def read(self, _limit): return json.dumps(self.payload).encode()


class CapturingOpener:
    def __init__(self): self.requests = []
    def __call__(self, request, timeout):
        self.requests.append((request, timeout))
        return Response({"status": "ok", "credential_reference": "profile-a", "api_secret": "MUST-NOT-LEAK"})


class SnmpUiClientTests(unittest.TestCase):
    def make_client(self):
        temp = tempfile.TemporaryDirectory()
        secret = Path(temp.name) / "api.secret"
        secret.write_bytes(b"x" * 64)
        os.chmod(secret, 0o600)
        opener = CapturingOpener()
        client = Edge1SnmpUiClient(secret_path=secret, opener=opener, now=lambda: 1800000000)
        self.addCleanup(temp.cleanup)
        return client, opener

    def test_origin_is_exact_loopback(self):
        with self.assertRaises(ValueError):
            Edge1SnmpUiClient(base_url="http://0.0.0.0:8112")

    def test_get_is_allowlisted_signed_and_sanitized(self):
        client, opener = self.make_client()
        status, payload = client.request("GET", "/api/snmp/events?limit=25", actor_subject="john")
        self.assertEqual(status, 200)
        self.assertEqual(payload["credential_reference"], "profile-a")
        self.assertNotIn("api_secret", payload)
        request, _timeout = opener.requests[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:8112/api/snmp/events?limit=25")
        self.assertTrue(request.headers.get("X-wwcx-signature") or request.headers.get("X-WWCX-Signature"))

    def test_arbitrary_path_and_trap_ingest_are_rejected(self):
        client, _ = self.make_client()
        with self.assertRaises(SnmpUiClientError):
            client.request("GET", "/etc/passwd", actor_subject="john")
        with self.assertRaises(SnmpUiClientError):
            client.request("POST", "/api/snmp/traps", actor_subject="john", payload={})

    def test_query_is_normalized(self):
        client, opener = self.make_client()
        client.request("GET", "/api/snmp/oids?q=ifHCInOctets", actor_subject="john")
        self.assertTrue(opener.requests[0][0].full_url.endswith("/api/snmp/oids?q=ifHCInOctets"))

    def test_sanitizer_keeps_reference_and_removes_secret_fields(self):
        value = sanitize_for_browser({
            "credential_reference": "router-prod-v3",
            "auth_passphrase": "hidden",
            "community": "hidden",
            "nested": {"private_key": "hidden", "status": "ready"},
        })
        self.assertEqual(value["credential_reference"], "router-prod-v3")
        self.assertNotIn("auth_passphrase", value)
        self.assertNotIn("community", value)
        self.assertEqual(value["nested"], {"status": "ready"})

    def test_sanitizer_redacts_secret_like_text_and_private_paths(self):
        value = sanitize_for_browser({
            "error": "profile failed password=hunter2 at /etc/edge1-snmp/profiles/router.json",
            "detail": "relay_secret: super-secret token=abcdef",
        })
        self.assertNotIn("hunter2", value["error"])
        self.assertNotIn("/etc/edge1-snmp", value["error"])
        self.assertIn("password=[REDACTED]", value["error"])
        self.assertIn("[PRIVATE_PATH]", value["error"])
        self.assertNotIn("super-secret", value["detail"])
        self.assertNotIn("abcdef", value["detail"])
        self.assertIn("relay_secret=[REDACTED]", value["detail"])
        self.assertIn("token=[REDACTED]", value["detail"])


if __name__ == "__main__":
    unittest.main()
