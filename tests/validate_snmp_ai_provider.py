#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

from edge1_snmp_ai import BigBirdPrivateAIProvider, SignedGatewayConfig, build_prompt, _sanitize_evidence


class FakeResponse:
    def __init__(self, request_id):
        self.status = 200
        self._body = json.dumps({"request_id": request_id, "answer": "evidence-based answer", "sources": []}).encode()
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self, _limit): return self._body


class ProviderTests(unittest.TestCase):
    def test_sanitizer_removes_secret_named_fields(self):
        clean = _sanitize_evidence({
            "device": "router-01", "credential_reference": "router-v3", "password": "x",
            "nested": {"community": "public", "metric": 7},
        })
        self.assertEqual(clean["device"], "router-01")
        self.assertNotIn("credential_reference", clean)
        self.assertNotIn("password", clean)
        self.assertNotIn("community", clean["nested"])
        self.assertEqual(clean["nested"]["metric"], 7)

    def test_prompt_preserves_fact_inference_boundary(self):
        prompt = build_prompt("Why is router-01 unreachable?", {"observed_facts": ["offline"]})
        self.assertIn("Never claim an inference is verified", prompt)
        self.assertIn("observed_facts", prompt)
        self.assertLessEqual(len(prompt.encode("utf-8")), 16384)

    def test_provider_uses_loopback_signed_gateway_contract(self):
        captured = {}
        def opener(request, timeout):
            captured["url"] = request.full_url
            captured["headers"] = dict(request.header_items())
            payload = json.loads(request.data.decode())
            captured["payload"] = payload
            return FakeResponse(payload["request_id"])
        provider = BigBirdPrivateAIProvider(
            SignedGatewayConfig(url="http://127.0.0.1:8787/v1/chat", key_id="test-key", secret="x" * 40),
            opener=opener,
        )
        result = provider.analyze(question="Summarize network health", evidence={"status": "ok"})
        self.assertEqual(result["provider"], "bigbird-private-ai")
        self.assertEqual(captured["url"], "http://127.0.0.1:8787/v1/chat")
        self.assertEqual(captured["payload"]["user"]["scopes"], ["chat:general"])
        self.assertFalse(captured["payload"]["include_communications"])
        self.assertTrue(any(k.lower() == "x-bb-signature" for k in captured["headers"]))

    def test_provider_rejects_non_loopback_endpoint(self):
        with self.assertRaises(Exception):
            BigBirdPrivateAIProvider(SignedGatewayConfig(url="https://example.com/v1/chat", key_id="k", secret="x" * 40))

    def test_systemd_credentials_supply_gateway_identity_without_environment_secret(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "bb_relay_key_id").write_text("runtime-key", encoding="utf-8")
            Path(tmp, "bb_relay_secret").write_text("s" * 40, encoding="utf-8")
            with patch.dict(os.environ, {"CREDENTIALS_DIRECTORY": tmp}, clear=True):
                config = SignedGatewayConfig.from_environment()
        self.assertEqual(config.key_id, "runtime-key")
        self.assertEqual(config.secret, "s" * 40)
        self.assertEqual(config.url, "http://127.0.0.1:8787/v1/chat")


if __name__ == "__main__":
    unittest.main(verbosity=2)
