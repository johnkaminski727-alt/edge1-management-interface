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

class AvaSemanticIntentEnvelopeTests(unittest.TestCase):
    def load(self):
        old = dict(os.environ)
        os.environ["BB_RELAY_KEY_ID"] = "test-key"
        os.environ["BB_RELAY_SECRET"] = "x" * 32
        spec = importlib.util.spec_from_file_location("ava_gateway_semantic_test", MODULE)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        os.environ.clear()
        os.environ.update(old)
        return module

    def test_semantic_envelope_accepts_allowed_blue_tit_effect(self):
        module = self.load()
        answer, effects = module._semantic_envelope({
            "answer": "I may have interpreted that request differently.",
            "ui_effects": ["blue_tit_easter_egg"],
        })
        self.assertTrue(answer)
        self.assertEqual(effects, ["blue_tit_easter_egg"])

    def test_blue_tit_prompt_requires_joke_aware_answer_guidance(self):
        module = self.load()
        import inspect

        source = inspect.getsource(module._call_openai)

        self.assertIn(
            "When you deliberately emit blue_tit_easter_egg",
            source,
        )
        self.assertIn(
            "instead of giving a generic refusal",
            source,
        )
        self.assertIn(
            "brief and non-graphic",
            source,
        )

    def test_semantic_envelope_drops_unknown_effects(self):
        module = self.load()
        answer, effects = module._semantic_envelope({
            "answer": "Safe answer.",
            "ui_effects": [
                "run_shell_command",
                "blue_tit_easter_egg",
                "enable_contacts",
                "blue_tit_easter_egg",
            ],
        })
        self.assertEqual(answer, "Safe answer.")
        self.assertEqual(effects, ["blue_tit_easter_egg"])

    def test_semantic_envelope_cannot_encode_capabilities(self):
        module = self.load()
        answer, effects = module._semantic_envelope({
            "answer": "Safe answer.",
            "ui_effects": ["contacts:write", "operator:actions:routine"],
            "requested_capabilities": ["contacts:write"],
            "scopes": ["operator:actions:routine"],
        })
        self.assertEqual(answer, "Safe answer.")
        self.assertEqual(effects, [])

    def test_semantic_envelope_requires_answer(self):
        module = self.load()
        with self.assertRaises(RuntimeError):
            module._semantic_envelope({
                "ui_effects": ["blue_tit_easter_egg"],
            })

    def test_plain_text_compatibility_has_no_ui_effects(self):
        module = self.load()
        answer, effects = module._semantic_envelope("Ordinary answer")
        self.assertEqual(answer, "Ordinary answer")
        self.assertEqual(effects, [])


if __name__ == "__main__":
    unittest.main()
