#!/usr/bin/env python3

import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "server/bigbird_edge1_control_plane.py"
SPEC = importlib.util.spec_from_file_location("bigbird_edge1_control_plane", MODULE_PATH)
CONTROL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONTROL)


class BigBirdControlPlaneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = CONTROL.load_manifest()
        cls.by_name = CONTROL.capability_map(cls.manifest)

    def test_enabled_read_capability_is_authorized(self):
        CONTROL.authorize_execution(self.manifest, self.by_name["edge1.repository.status"])

    def test_disabled_privileged_capability_is_rejected(self):
        with self.assertRaisesRegex(CONTROL.ControlPlaneError, "disabled"):
            CONTROL.authorize_execution(self.manifest, self.by_name["edge1.repository.fetch"])

    def test_migration_mode_rejects_enabled_mutation(self):
        manifest = copy.deepcopy(self.manifest)
        capability = copy.deepcopy(self.by_name["edge1.repository.fetch"])
        capability["enabled"] = True
        with self.assertRaisesRegex(CONTROL.ControlPlaneError, "migration mode"):
            CONTROL.authorize_execution(manifest, capability)

    def test_read_client_rejects_non_read_even_after_migration(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["mode"] = "active"
        capability = copy.deepcopy(self.by_name["edge1.repository.fetch"])
        capability["enabled"] = True
        with self.assertRaisesRegex(CONTROL.ControlPlaneError, "only executes read"):
            CONTROL.authorize_execution(manifest, capability)

    def test_operations_broker_must_be_exact_loopback_endpoint(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["brokers"]["operations_api"]["base_url"] = "http://0.0.0.0:8097"
        with self.assertRaisesRegex(CONTROL.ControlPlaneError, "loopback-bound"):
            CONTROL.operations_broker(manifest)

    def test_unknown_capability_is_rejected_before_network_call(self):
        with self.assertRaisesRegex(CONTROL.ControlPlaneError, "unknown capability"):
            CONTROL.run_capability(self.manifest, "edge1.unknown")


if __name__ == "__main__":
    unittest.main()
