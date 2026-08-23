#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import pathlib
import unittest
from unittest import mock

from server import ava_operations_reader as reader
from server import bigbird_edge1_control_plane as control_plane

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROFILE = json.loads((ROOT / "integrations/ava-operations-reader/profile-v1.json").read_text())
TOOLS = json.loads((ROOT / "integrations/ava-operations-reader/tool-manifest-v1.json").read_text())
MANIFEST = json.loads((ROOT / "integrations/bigbird-edge1-control-plane/capabilities-v2.json").read_text())


class AvaOperationsReaderTests(unittest.TestCase):
    def test_profile_is_read_only_and_has_complete_denials(self):
        self.assertEqual(PROFILE["mode"], "read_only")
        self.assertEqual(
            set(PROFILE["forbidden_classes"]),
            {"staged_write", "staged_write_apply", "privileged_action"},
        )
        self.assertLessEqual(PROFILE["max_age_seconds"], 300)

    def test_selected_capabilities_exist_and_are_enabled_reads(self):
        selected = reader.validate_contract(PROFILE, MANIFEST, TOOLS)
        self.assertEqual(list(selected), PROFILE["capabilities"])
        for item in selected.values():
            self.assertEqual(item["class"], "read")
            self.assertTrue(item["enabled"])
            self.assertEqual(item["backend"], "operations_api")

    def test_tool_manifest_accepts_no_caller_input(self):
        self.assertEqual([item["name"] for item in TOOLS["tools"]], PROFILE["capabilities"])
        for tool in TOOLS["tools"]:
            self.assertTrue(tool["read_only"])
            self.assertEqual(
                tool["input_schema"],
                {"type": "object", "properties": {}, "additionalProperties": False},
            )

    def test_no_mutation_or_escape_capabilities_are_selected(self):
        forbidden_tokens = {"stage", "apply", "reload", "deploy", "fetch", "write", "shell", "exec"}
        for name in PROFILE["capabilities"]:
            self.assertFalse(set(name.split(".")) & forbidden_tokens, name)

    def test_contract_drift_fails_closed(self):
        broken = copy.deepcopy(MANIFEST)
        by_name = {item["name"]: item for item in broken["capabilities"]}
        by_name[PROFILE["capabilities"][0]]["class"] = "privileged_action"
        with self.assertRaises(reader.AvaOperationsReaderError):
            reader.validate_contract(PROFILE, broken, TOOLS)

    def test_scope_drift_fails_closed(self):
        broken = copy.deepcopy(TOOLS)
        broken["tools"][0]["scope"] = "edge1.everything"
        with self.assertRaises(reader.AvaOperationsReaderError):
            reader.validate_contract(PROFILE, MANIFEST, broken)

    def test_extra_input_schema_fails_closed(self):
        broken = copy.deepcopy(TOOLS)
        broken["tools"][0]["input_schema"]["properties"]["command"] = {"type": "string"}
        with self.assertRaises(reader.AvaOperationsReaderError):
            reader.validate_contract(PROFILE, MANIFEST, broken)

    @mock.patch.object(reader, "utc_now", return_value="2026-08-23T08:00:00Z")
    @mock.patch.object(control_plane, "discover")
    @mock.patch.object(control_plane, "run_capability")
    def test_run_preserves_audit_and_parses_json(self, run_capability, discover, _utc_now):
        discover.return_value = {
            "health": {"status": "ok", "mutations_enabled": False},
            "capabilities": [{
                "name": "edge1.bigbird.health.read",
                "available": True,
                "broker_mutating": False,
            }],
        }
        run_capability.return_value = {
            "event_id": "audit-123",
            "status": "succeeded",
            "duration_ms": 7,
            "exit_code": 0,
            "stdout": '{"status":"ok"}',
            "stderr": "",
        }
        selected = reader.validate_contract(PROFILE, MANIFEST, TOOLS)
        with mock.patch.object(reader, "contracts", return_value=(PROFILE, MANIFEST, TOOLS, selected)):
            result = reader.run("edge1.bigbird.health.read")
        self.assertTrue(result["read_only"])
        self.assertEqual(result["audit"]["event_id"], "audit-123")
        self.assertEqual(result["data"], {"format": "json", "value": {"status": "ok"}})
        self.assertEqual(result["freshness"]["max_age_seconds"], 60)
        self.assertEqual(result["observed_at_utc"], "2026-08-23T08:00:00Z")

    @mock.patch.object(reader, "utc_now", return_value="2026-08-23T08:00:00Z")
    @mock.patch.object(control_plane, "discover")
    def test_capability_discovery_is_versioned_and_reports_availability(self, discover, _utc_now):
        discover.return_value = {
            "health": {"status": "ok", "mutations_enabled": False},
            "capabilities": [
                {"name": name, "available": True, "broker_mutating": False}
                for name in PROFILE["capabilities"]
            ],
        }
        selected = reader.validate_contract(PROFILE, MANIFEST, TOOLS)
        with mock.patch.object(reader, "contracts", return_value=(PROFILE, MANIFEST, TOOLS, selected)):
            result = reader.capabilities()
        self.assertEqual(result["schema_version"], 1)
        self.assertEqual(result["profile"], "ava-operations-reader")
        self.assertEqual(result["mode"], "read_only")
        self.assertTrue(all(item["available"] for item in result["capabilities"]))
        self.assertFalse(result["broker_health"]["mutations_enabled"])

    def test_unselected_capability_is_denied_before_broker_call(self):
        selected = reader.validate_contract(PROFILE, MANIFEST, TOOLS)
        with mock.patch.object(reader, "contracts", return_value=(PROFILE, MANIFEST, TOOLS, selected)), \
             mock.patch.object(control_plane, "run_capability") as run_capability:
            with self.assertRaises(reader.AvaOperationsReaderError):
                reader.run("edge1.files.stage")
        run_capability.assert_not_called()

    def test_live_broker_mutation_drift_fails_closed(self):
        discovery = {
            "health": {"status": "ok", "mutations_enabled": False},
            "capabilities": [{
                "name": "edge1.services.read",
                "available": True,
                "broker_mutating": True,
            }],
        }
        with self.assertRaises(reader.AvaOperationsReaderError):
            reader.validate_live_capability(discovery, "edge1.services.read")

    def test_enabled_broker_mutations_fail_closed(self):
        discovery = {
            "health": {"status": "ok", "mutations_enabled": True},
            "capabilities": [{
                "name": "edge1.services.read",
                "available": True,
                "broker_mutating": False,
            }],
        }
        with self.assertRaises(reader.AvaOperationsReaderError):
            reader.validate_live_capability(discovery, "edge1.services.read")


if __name__ == "__main__":
    unittest.main()
