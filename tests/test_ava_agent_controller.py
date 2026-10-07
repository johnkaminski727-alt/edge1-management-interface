#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "server" / "ava_agent_controller.py"
SPEC = importlib.util.spec_from_file_location("ava_agent_controller", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
agent = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = agent
SPEC.loader.exec_module(agent)


def base_payload() -> dict:
    return {
        "request_id": "a" * 32,
        "user": {"id": "u", "role": "internal_viewer", "scopes": [
            "chat:general", "edge1:status:read", "library:search", "library:document:read",
            "mail:read", "communications:read", "contacts:read", "telephony:read",
        ]},
        "message": "Check Edge1 health and find the latest project documentation",
        "include_edge1_status": True,
        "include_library": True,
        "include_documentation": True,
        "library_collections": ["operations"],
        "include_mail": True,
        "include_communications": True,
        "communications_groups": ["ops"],
        "include_contacts": True,
        "include_telephony": True,
    }


class AvaAgentControllerTests(unittest.TestCase):
    def test_explicit_mode_preserves_enabled_sources(self) -> None:
        payload = base_payload()
        plan = agent.build_plan(payload)
        self.assertFalse(plan.auto_route)
        self.assertTrue(all(plan.source_flags.values()))
        prepared = agent.prepare_gateway_request(payload, plan)
        self.assertEqual(prepared["user"]["scopes"], payload["user"]["scopes"])

    def test_auto_route_only_reduces_authorized_sources(self) -> None:
        payload = base_payload()
        payload["agent_auto_route"] = True
        plan = agent.build_plan(payload)
        self.assertTrue(plan.source_flags["include_edge1_status"])
        self.assertTrue(plan.source_flags["include_library"])
        self.assertTrue(plan.source_flags["include_documentation"])
        self.assertFalse(plan.source_flags["include_communications"])
        self.assertFalse(plan.source_flags["include_contacts"])
        self.assertFalse(plan.source_flags["include_telephony"])
        prepared = agent.prepare_gateway_request(payload, plan)
        self.assertNotIn("agent_auto_route", prepared)
        self.assertNotIn("communications:read", prepared["user"]["scopes"])
        self.assertNotIn("contacts:read", prepared["user"]["scopes"])
        self.assertNotIn("telephony:read", prepared["user"]["scopes"])
        self.assertEqual(prepared["communications_groups"], [])

    def test_auto_route_separates_mail_room_from_communications_relay(self) -> None:
        payload = base_payload()
        payload["agent_auto_route"] = True
        payload["routing_message"] = "Triage the inbox"
        plan = agent.build_plan(payload)
        self.assertTrue(plan.source_flags["include_mail"])
        self.assertFalse(plan.source_flags["include_communications"])
        prepared = agent.prepare_gateway_request(payload, plan)
        self.assertIn("mail:read", prepared["user"]["scopes"])
        self.assertNotIn("communications:read", prepared["user"]["scopes"])

        payload["routing_message"] = "Check the NNTP news relay"
        plan = agent.build_plan(payload)
        self.assertFalse(plan.source_flags["include_mail"])
        self.assertTrue(plan.source_flags["include_communications"])

    def test_auto_route_selects_contacts_for_directory_lookup(self) -> None:
        payload = base_payload()
        payload["message"] = "Who is this phone number in the contact directory?"
        payload["agent_auto_route"] = True
        plan = agent.build_plan(payload)
        self.assertTrue(plan.source_flags["include_contacts"])
        prepared = agent.prepare_gateway_request(payload, plan)
        self.assertIn("contacts:read", prepared["user"]["scopes"])
        self.assertFalse(prepared["include_library"])
        self.assertEqual(prepared["library_collections"], [])

    def test_contact_evidence_is_counted(self) -> None:
        payload = base_payload()
        plan = agent.build_plan(payload)
        trace = agent.verify_gateway_result(payload["request_id"], {
            "request_id": payload["request_id"],
            "answer": "A matching contact was found.",
            "mode": "read-only",
            "contact_sources": [{"source_id": "contact:1", "title": "Unified Contacts"}],
        }, plan)
        self.assertEqual(trace["evidence"]["contacts"], 1)
        self.assertEqual(trace["evidence_class"], "source-backed")

    def test_library_collections_are_normalized_and_bounded(self) -> None:
        payload = base_payload()
        payload["library_collections"] = ["Operations", "operations"]
        plan = agent.build_plan(payload)
        prepared = agent.prepare_gateway_request(payload, plan)
        self.assertEqual(prepared["library_collections"], ["operations"])

        payload["library_collections"] = ["../secret"]
        plan = agent.build_plan(payload)
        with self.assertRaises(agent.AgentControllerError):
            agent.prepare_gateway_request(payload, plan)

    def test_library_collections_require_library_access(self) -> None:
        payload = base_payload()
        payload["include_library"] = False
        payload["library_collections"] = ["operations"]
        plan = agent.build_plan(payload)
        with self.assertRaises(agent.AgentControllerError):
            agent.prepare_gateway_request(payload, plan)

    def test_controller_never_expands_disabled_source(self) -> None:
        payload = base_payload()
        payload["include_edge1_status"] = False
        payload["agent_auto_route"] = True
        plan = agent.build_plan(payload)
        self.assertFalse(plan.source_flags["include_edge1_status"])

    def test_plan_is_bounded_and_has_verification(self) -> None:
        plan = agent.build_plan(base_payload())
        self.assertLessEqual(len(plan.steps), agent.MAX_STEPS)
        self.assertEqual(plan.steps[0].step_id, "understand")
        self.assertEqual(plan.steps[-1].step_id, "verify")

    def test_verification_accepts_read_only_source_backed_result(self) -> None:
        payload = base_payload()
        plan = agent.build_plan(payload)
        trace = agent.verify_gateway_result(payload["request_id"], {
            "request_id": payload["request_id"],
            "answer": "Edge1 is healthy.",
            "mode": "read-only",
            "sources": [{"source_id": "x", "title": "Status"}],
        }, plan)
        self.assertEqual(trace["verification"], "passed")
        self.assertEqual(trace["evidence_class"], "source-backed")

    def test_verification_rejects_write_mode_or_sensitive_field(self) -> None:
        payload = base_payload()
        plan = agent.build_plan(payload)
        with self.assertRaises(agent.AgentControllerError):
            agent.verify_gateway_result(payload["request_id"], {
                "request_id": payload["request_id"], "answer": "ok", "mode": "write",
            }, plan)
        with self.assertRaises(agent.AgentControllerError):
            agent.verify_gateway_result(payload["request_id"], {
                "request_id": payload["request_id"], "answer": "ok", "mode": "read-only",
                "sources": [{"token": "forbidden"}],
            }, plan)


    def test_v2_ui_effect_allowlist_is_exact(self) -> None:
        self.assertEqual(
            agent.ALLOWED_UI_EFFECTS,
            frozenset({
                "blue_tit_easter_egg",
                "donkey_easter_egg",
                "cat_easter_egg",
                "moist_owlette_easter_egg",
            }),
        )

    def test_v2_ui_effects_are_independently_preserved(self) -> None:
        expected = [
            "blue_tit_easter_egg",
            "donkey_easter_egg",
            "cat_easter_egg",
            "moist_owlette_easter_egg",
        ]
        result = agent.sanitize_gateway_result({
            "answer": "Presentation request accepted.",
            "ui_effects": expected + ["operator:actions:routine"],
        })
        self.assertEqual(result["ui_effects"], expected)

    def test_ui_effects_are_independently_allowlisted(self) -> None:
        result = agent.sanitize_gateway_result({
            "request_id": "a" * 32,
            "answer": "Safe answer.",
            "mode": "read-only",
            "ui_effects": [
                "run_shell_command",
                "blue_tit_easter_egg",
                "contacts:write",
                "blue_tit_easter_egg",
            ],
        })
        self.assertEqual(result["ui_effects"], ["blue_tit_easter_egg"])

    def test_ui_effects_malformed_value_fails_closed(self) -> None:
        for value in (
            None,
            "blue_tit_easter_egg",
            {"effect": "blue_tit_easter_egg"},
            123,
        ):
            result = agent.sanitize_gateway_result({
                "request_id": "a" * 32,
                "answer": "Safe answer.",
                "mode": "read-only",
                "ui_effects": value,
            })
            self.assertEqual(result["ui_effects"], [])

    def test_ui_effect_sanitizer_does_not_mutate_gateway_result(self) -> None:
        original = {
            "request_id": "a" * 32,
            "answer": "Safe answer.",
            "mode": "read-only",
            "ui_effects": ["blue_tit_easter_egg", "operator:actions:routine"],
        }
        sanitized = agent.sanitize_gateway_result(original)

        self.assertIsNot(original, sanitized)
        self.assertEqual(
            original["ui_effects"],
            ["blue_tit_easter_egg", "operator:actions:routine"],
        )
        self.assertEqual(
            sanitized["ui_effects"],
            ["blue_tit_easter_egg"],
        )



if __name__ == "__main__":
    unittest.main()
