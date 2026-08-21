#!/usr/bin/env python3
"""Cross-check BigBird Control Plane v2 tool and capability manifests."""

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAPABILITIES = ROOT / "integrations/bigbird-edge1-control-plane/capabilities-v2.json"
TOOLS = ROOT / "integrations/bigbird-edge1-control-plane/tool-manifest-v2.json"


class BigBirdControlPlaneToolManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.capability_manifest = json.loads(CAPABILITIES.read_text(encoding="utf-8"))
        cls.tool_manifest = json.loads(TOOLS.read_text(encoding="utf-8"))
        cls.capabilities = {item["name"]: item for item in cls.capability_manifest["capabilities"]}
        cls.tools = cls.tool_manifest["tools"]

    def test_identity_and_mode_match(self):
        self.assertEqual(self.tool_manifest["version"], 2)
        self.assertEqual(self.tool_manifest["integration"], "bigbird-edge1-control-plane")
        self.assertEqual(self.tool_manifest["mode"], self.capability_manifest["mode"])
        self.assertEqual(self.tool_manifest["dispatcher"], "run_capability")

    def test_tool_names_are_unique(self):
        names = [tool["name"] for tool in self.tools]
        self.assertEqual(len(names), len(set(names)))

    def test_each_tool_maps_to_existing_capability_with_same_scope_and_enablement(self):
        for tool in self.tools:
            capability = self.capabilities.get(tool["capability"])
            self.assertIsNotNone(capability, tool["name"])
            self.assertEqual(tool["name"], capability["name"])
            self.assertEqual(tool["scope"], capability["scope"], tool["name"])
            self.assertEqual(tool["enabled"], capability["enabled"], tool["name"])

    def test_read_only_annotation_matches_capability_class(self):
        for tool in self.tools:
            capability = self.capabilities[tool["capability"]]
            self.assertEqual(tool["read_only"], capability["class"] == "read", tool["name"])

    def test_mutating_tools_repeat_exact_mutation_policy(self):
        for tool in self.tools:
            if tool["read_only"]:
                continue
            capability = self.capabilities[tool["capability"]]
            self.assertEqual(tool["mutation_policy"], capability["mutation_policy"], tool["name"])
            self.assertFalse(tool.get("destructive", True), tool["name"])

    def test_migration_exposes_only_stage_only_write(self):
        if self.tool_manifest["mode"] != "migration":
            self.skipTest("migration-only policy")
        enabled_writes = [tool["name"] for tool in self.tools if tool["enabled"] and not tool["read_only"]]
        self.assertEqual(enabled_writes, ["edge1.files.stage"])

    def test_repository_branch_write_and_deploy_are_not_collapsed(self):
        branch_write = self.capabilities["edge1.repository.branch.write"]
        deploy = self.capabilities["edge1.repository.fast_forward_main"]
        self.assertNotEqual(branch_write["scope"], deploy["scope"])
        tool = next(item for item in self.tools if item["name"] == "edge1.repository.branch.write")
        self.assertFalse(tool["enabled"])
        self.assertEqual(tool["input_schema"]["properties"]["branch"]["pattern"],
                         "^agent/bigbird-[a-z0-9][a-z0-9._-]{0,79}$")

    def test_filesystem_apply_remains_disabled(self):
        tool = next(item for item in self.tools if item["name"] == "edge1.files.apply")
        self.assertFalse(tool["enabled"])
        self.assertEqual(tool["scope"], "edge1.files.apply")


if __name__ == "__main__":
    unittest.main()
