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
            "communications:read", "telephony:read",
        ]},
        "message": "Check Edge1 health and find the latest project documentation",
        "include_edge1_status": True,
        "include_library": True,
        "include_documentation": True,
        "library_collections": ["operations"],
        "include_communications": True,
        "communications_groups": ["ops"],
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
        self.assertFalse(plan.source_flags["include_telephony"])
        prepared = agent.prepare_gateway_request(payload, plan)
        self.assertNotIn("agent_auto_route", prepared)
        self.assertNotIn("communications:read", prepared["user"]["scopes"])
        self.assertNotIn("telephony:read", prepared["user"]["scopes"])
        self.assertEqual(prepared["communications_groups"], [])

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


if __name__ == "__main__":
    unittest.main()
