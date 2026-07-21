#!/usr/bin/env python3

import hashlib
import hmac
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server" / "portal"))

import portal_api_server as api  # noqa: E402
from carrier_workflows import (  # noqa: E402
    WorkflowIdentity,
    WorkflowValidationError,
    create_change_request,
    create_ticket,
)


class HeaderMap(dict):
    def get(self, key, default=None):
        return super().get(key, default)


class CarrierWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.identity = WorkflowIdentity("carrier-client", "carrier-alpha")

    def tearDown(self):
        self.temp.cleanup()

    def test_ticket_is_append_only_and_carrier_owned(self):
        path = self.root / "tickets.jsonl"
        record = create_ticket(path, self.identity, {
            "category": "incident",
            "priority": "high",
            "summary": "Inbound call failures",
            "description": "Investigate repeated 503 responses.",
            "reference": "INC-1001",
        })
        self.assertEqual(record["carrier_id"], "carrier-alpha")
        self.assertEqual(record["status"], "open")
        self.assertTrue(record["ticket_id"].startswith("TKT-"))
        stored = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(stored, record)

    def test_change_request_never_authorizes_execution(self):
        path = self.root / "changes.jsonl"
        record = create_change_request(path, self.identity, {
            "category": "capacity_change",
            "summary": "Increase test capacity",
            "description": "Request review of a higher non-production channel limit.",
        })
        self.assertEqual(record["status"], "requested")
        self.assertFalse(record["execution_authorized"])
        self.assertTrue(record["change_request_id"].startswith("CRQ-"))

    def test_invalid_category_is_rejected(self):
        with self.assertRaises(WorkflowValidationError):
            create_ticket(self.root / "tickets.jsonl", self.identity, {
                "category": "credential_rotation",
                "summary": "Unsupported",
                "description": "Unsupported category.",
            })

    def test_unsafe_reference_is_rejected(self):
        with self.assertRaises(WorkflowValidationError):
            create_ticket(self.root / "tickets.jsonl", self.identity, {
                "category": "general",
                "summary": "Reference validation",
                "description": "Reject unsafe references.",
                "reference": "../../secret file",
            })

    def test_body_digest_is_required_for_post_authentication(self):
        body = b'{"summary":"test"}'
        timestamp = str(int(time.time()))
        secret = "test-secret"
        client = "carrier-client"
        digest = hashlib.sha256(body).hexdigest()
        signature = hmac.new(
            secret.encode(),
            (client + timestamp + digest).encode(),
            hashlib.sha256,
        ).hexdigest()
        policy = self.root / "policy.json"
        creds = self.root / "creds.json"
        policy.write_text(json.dumps({
            "enabled": True,
            "timestamp_window_seconds": 300,
            "allowed_clients": [client],
        }), encoding="utf-8")
        creds.write_text(json.dumps({"clients": {client: {
            "secret": secret,
            "carrier_id": "carrier-alpha",
            "scopes": ["carrier.ticket.create"],
        }}}), encoding="utf-8")
        headers = HeaderMap({
            "X-Portal-Client": client,
            "X-Portal-Timestamp": timestamp,
            "X-Portal-Signature": signature,
            "X-Portal-Content-SHA256": digest,
        })
        with patch.object(api, "POLICY", policy), patch.object(api, "CREDS", creds):
            identity = api.authenticate_request(headers, body)
            self.assertIsNotNone(identity)
            self.assertEqual(identity.carrier_id, "carrier-alpha")
            headers.pop("X-Portal-Content-SHA256")
            self.assertIsNone(api.authenticate_request(headers, body))

    def test_tampered_body_is_rejected(self):
        original = b'{"summary":"original"}'
        tampered = b'{"summary":"tampered"}'
        timestamp = str(int(time.time()))
        secret = "test-secret"
        client = "carrier-client"
        digest = hashlib.sha256(original).hexdigest()
        signature = hmac.new(
            secret.encode(),
            (client + timestamp + digest).encode(),
            hashlib.sha256,
        ).hexdigest()
        policy = self.root / "policy.json"
        creds = self.root / "creds.json"
        policy.write_text(json.dumps({
            "enabled": True,
            "timestamp_window_seconds": 300,
            "allowed_clients": [client],
        }), encoding="utf-8")
        creds.write_text(json.dumps({"clients": {client: {
            "secret": secret,
            "carrier_id": "carrier-alpha",
            "scopes": ["carrier.ticket.create"],
        }}}), encoding="utf-8")
        headers = HeaderMap({
            "X-Portal-Client": client,
            "X-Portal-Timestamp": timestamp,
            "X-Portal-Signature": signature,
            "X-Portal-Content-SHA256": digest,
        })
        with patch.object(api, "POLICY", policy), patch.object(api, "CREDS", creds):
            self.assertIsNone(api.authenticate_request(headers, tampered))

    def test_get_authentication_remains_backward_compatible(self):
        timestamp = str(int(time.time()))
        secret = "test-secret"
        client = "legacy-client"
        signature = hmac.new(
            secret.encode(),
            (client + timestamp).encode(),
            hashlib.sha256,
        ).hexdigest()
        policy = self.root / "policy.json"
        creds = self.root / "creds.json"
        policy.write_text(json.dumps({
            "enabled": True,
            "timestamp_window_seconds": 300,
            "allowed_clients": [client],
        }), encoding="utf-8")
        creds.write_text(json.dumps({"clients": {client: {
            "secret": secret,
        }}}), encoding="utf-8")
        headers = HeaderMap({
            "X-Portal-Client": client,
            "X-Portal-Timestamp": timestamp,
            "X-Portal-Signature": signature,
        })
        with patch.object(api, "POLICY", policy), patch.object(api, "CREDS", creds):
            self.assertIsNotNone(api.authenticate_request(headers))


if __name__ == "__main__":
    unittest.main()
