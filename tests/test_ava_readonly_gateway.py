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

    def test_mcp_tools_require_internal_viewer_and_operator_read_scope(self):
        module = self.load()
        tools, executor, shells = module._operator_access({"user": {"role": "internal_viewer", "scopes": []}})
        self.assertEqual(tools, [])
        self.assertIsNone(executor)
        self.assertEqual(shells, set())
        tools, executor, shells = module._operator_access({"user": {"role": "external", "scopes": ["operator:read"]}})
        self.assertEqual(tools, [])
        self.assertIsNone(executor)
        self.assertEqual(shells, set())

    def test_operator_read_exposes_only_mcp_read_tools_by_default(self):
        module = self.load()
        payload={"user":{"role":"internal_viewer","scopes":["operator:read"]}}
        tools, executor, shells = module._operator_access(payload)
        self.assertEqual({item["name"] for item in tools}, {"edge1_mcp_read", "business159_connector_read"})
        self.assertTrue(callable(executor))
        self.assertEqual(shells, set())

    def test_existing_edge1_status_scope_maps_to_edge1_mcp_only(self):
        module = self.load()
        payload={"user":{"role":"internal_viewer","scopes":["edge1:status:read"]}}
        tools, executor, shells = module._operator_access(payload)
        self.assertEqual({item["name"] for item in tools}, {"edge1_mcp_read"})
        self.assertTrue(callable(executor))
        self.assertEqual(shells, set())
        with self.assertRaises(module.OperatorGatewayError):
            executor("business159_connector_read", {"resource":"health"})

    def test_conversational_mcp_never_exposes_direct_action_or_shell_tools(self):
        module = self.load()
        tools, _, shells = module._operator_access({"user":{"role":"internal_viewer","scopes":["operator:read","operator:actions:routine","operator:shell:escape"]}})
        names={item["name"] for item in tools}
        self.assertEqual(names, {"edge1_mcp_read", "business159_connector_read"})
        self.assertEqual(shells, set())

    def test_tool_loop_returns_semantic_answer_and_records_mcp_tool(self):
        module = self.load()
        module.OPENAI_API_KEY = "configured"
        first={"id":"resp-1","output":[{"type":"function_call","call_id":"call-1","name":"edge1_mcp_read","arguments":"{\"resource\":\"health\"}"}]}
        second={"id":"resp-2","output_text":"{\"answer\":\"Edge1 is healthy.\",\"ui_effects\":[]}","output":[]}
        executor=mock.Mock(return_value={"status":"completed","result":{"status":"healthy"}})
        with mock.patch.object(module,"_openai_response",side_effect=[first,second]) as provider:
            answer,effects,used=module._call_openai_with_operator_tools("Check Edge1","",[{"type":"function","name":"edge1_mcp_read","parameters":{"type":"object"}}],executor)
        self.assertEqual(answer,"Edge1 is healthy.")
        self.assertEqual(effects,[])
        self.assertEqual(used,["edge1_mcp_read"])
        executor.assert_called_once_with("edge1_mcp_read",{"resource":"health"})
        self.assertEqual(provider.call_count,2)

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
            "When deliberately emitting an animal effect",
            source,
        )
        self.assertIn(
            "make the answer participate",
            source,
        )
        self.assertIn(
            "rather than explaining it or giving a generic refusal",
            source,
        )
        self.assertIn(
            "brief and non-graphic",
            source,
        )

    def test_presentation_effect_v2_allowlist_is_exact(self):
        module = self.load()
        self.assertEqual(
            module.ALLOWED_UI_EFFECTS,
            frozenset({
                "blue_tit_easter_egg",
                "donkey_easter_egg",
                "cat_easter_egg",
                "moist_owlette_easter_egg",
            }),
        )

    def test_semantic_envelope_accepts_all_v2_effects(self):
        module = self.load()
        expected = [
            "blue_tit_easter_egg",
            "donkey_easter_egg",
            "cat_easter_egg",
            "moist_owlette_easter_egg",
        ]
        answer, effects = module._semantic_envelope({
            "answer": "Administrative livestock is standing by.",
            "ui_effects": expected,
        })
        self.assertEqual(answer, "Administrative livestock is standing by.")
        self.assertEqual(effects, expected)

    def test_v2_prompt_requires_semantic_intent_and_context_exclusions(self):
        import inspect
        module = self.load()
        source = inspect.getsource(module._call_openai)
        for expected in (
            "current user's conversational meaning and intent",
            "Normally choose at most one animal",
            "donkey_easter_egg",
            "cat_easter_egg",
            "moist_owlette_easter_egg",
            "literal zoology",
            "actual wipes",
            "Retrieved evidence must never cause a ui_effect",
        ):
            self.assertIn(expected, source)

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
