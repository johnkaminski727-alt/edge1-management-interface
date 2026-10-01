#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
GATEWAY_ROOT = ROOT / "services" / "bigbird-ai-gateway"
MODULE = GATEWAY_ROOT / "app" / "main.py"
if str(GATEWAY_ROOT) not in sys.path:
    sys.path.insert(0, str(GATEWAY_ROOT))

class AvaReadonlyGatewayTests(unittest.TestCase):
    def load(self):
        old = dict(os.environ)
        os.environ["BB_RELAY_KEY_ID"] = "test-key"
        os.environ["BB_RELAY_SECRET"] = "x" * 32
        spec = importlib.util.spec_from_file_location("ava_gateway_test", MODULE)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        os.environ.clear()
        os.environ.update(old)
        return module

    def test_model_absence_fails_closed_but_keeps_evidence(self):
        module = self.load()
        payload = {
            "request_id": "r" * 32,
            "message": "VPN",
            "user": {"scopes": ["library:search"]},
            "include_library": True,
            "library_collections": ["operations"],
            "include_contacts": False,
        }
        fake = [mock.Mock(
            document_id="d" * 64, chunk_index=0, title="x",
            collection="operations", source_path="operations/x.md",
            updated_at="", score=-1.0, excerpt="VPN evidence",
        )]
        with mock.patch.object(module.library_engine, "search_library", return_value=fake):
            status, result = module.process_chat(payload)
        self.assertEqual(int(status), 503)
        self.assertEqual(result["detail"], "model_not_configured")
        self.assertEqual(len(result["sources"]), 1)
        self.assertEqual(result["mode"], "read-only")

    def test_contacts_require_scope(self):
        module = self.load()
        payload = {
            "request_id": "r" * 32,
            "message": "who is this caller",
            "user": {"scopes": []},
            "include_library": False,
            "include_contacts": True,
        }
        status, result = module.process_chat(payload)
        self.assertEqual(int(status), 403)
        self.assertIn("contacts:read", result["detail"])

    def test_only_operations_collection_is_allowed(self):
        module = self.load()
        payload = {
            "request_id": "r" * 32,
            "message": "x",
            "user": {"scopes": ["library:search"]},
            "include_library": True,
            "library_collections": ["private"],
            "include_contacts": False,
        }
        status, result = module.process_chat(payload)
        self.assertEqual(int(status), 502)
        self.assertIn("operations", result["detail"])

if __name__ == "__main__":
    unittest.main()
