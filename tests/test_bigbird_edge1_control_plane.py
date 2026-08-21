#!/usr/bin/env python3

import copy
import importlib.util
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "server/bigbird_edge1_control_plane.py"
os.environ["BIGBIRD_CONTROL_PLANE_ROOT"] = str(ROOT)
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

    def test_migration_mode_allows_stage_only_filesystem_capability(self):
        CONTROL.authorize_execution(self.manifest, self.by_name["edge1.files.stage"])

    def test_migration_mode_rejects_enabled_privileged_mutation(self):
        manifest = copy.deepcopy(self.manifest)
        capability = copy.deepcopy(self.by_name["edge1.repository.fetch"])
        capability["enabled"] = True
        with self.assertRaisesRegex(CONTROL.ControlPlaneError, "only stage-only filesystem writes"):
            CONTROL.authorize_execution(manifest, capability)

    def test_active_mode_still_rejects_unimplemented_privileged_class(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["mode"] = "active"
        capability = copy.deepcopy(self.by_name["edge1.repository.fetch"])
        capability["enabled"] = True
        with self.assertRaisesRegex(CONTROL.ControlPlaneError, "not executable"):
            CONTROL.authorize_execution(manifest, capability)

    def test_operations_broker_must_be_exact_loopback_endpoint(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["brokers"]["operations_api"]["base_url"] = "http://0.0.0.0:8097"
        with self.assertRaisesRegex(CONTROL.ControlPlaneError, "loopback-bound"):
            CONTROL.operations_broker(manifest)

    def test_unknown_capability_is_rejected_before_network_call(self):
        with self.assertRaisesRegex(CONTROL.ControlPlaneError, "unknown capability"):
            CONTROL.run_capability(self.manifest, "edge1.unknown")

    def test_stage_rejects_target_outside_docs_before_backend_call(self):
        params = {
            "target": "/etc/ssh/sshd_config",
            "content": "candidate\n",
            "actor": "test",
            "reason": "test reject",
        }
        with mock.patch.object(CONTROL, "run_fsctl_stage") as backend:
            with self.assertRaisesRegex(CONTROL.ControlPlaneError, "approved Edge1 docs path"):
                CONTROL.run_capability(self.manifest, "edge1.files.stage", params)
            backend.assert_not_called()

    def test_stage_rejects_unexpected_fields(self):
        params = {
            "target": "/opt/edge1-management-interface/docs/test.md",
            "content": "candidate\n",
            "actor": "test",
            "reason": "test reject",
            "apply": True,
        }
        with self.assertRaisesRegex(CONTROL.ControlPlaneError, "unexpected filesystem stage input"):
            CONTROL.run_capability(self.manifest, "edge1.files.stage", params)

    def test_stage_dispatches_only_to_stage_backend(self):
        params = {
            "target": "/opt/edge1-management-interface/docs/test.md",
            "content": "candidate\n",
            "actor": "test",
            "reason": "unit test",
        }
        stage = {
            "status": "staged",
            "stage_id": "20260821T020000Z-0123456789ab",
            "target": params["target"],
        }
        with mock.patch.object(CONTROL, "run_fsctl_stage", return_value=stage) as backend:
            result = CONTROL.run_capability(self.manifest, "edge1.files.stage", params)
        backend.assert_called_once_with(params)
        self.assertEqual(result["stage"], stage)
        self.assertEqual(result["mutation_policy"], "stage_only")
        self.assertIn("approve", result["next_step"].lower())

    def test_backend_availability_requires_executable_fsctl(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp) / "bigbird-fsctl"
            fake.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            fake.chmod(stat.S_IRUSR | stat.S_IWUSR)
            with mock.patch.object(CONTROL, "FSCTL", fake):
                self.assertFalse(CONTROL.backend_available("filesystem_write_connector"))
            fake.chmod(stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
            with mock.patch.object(CONTROL, "FSCTL", fake):
                self.assertTrue(CONTROL.backend_available("filesystem_write_connector"))


if __name__ == "__main__":
    unittest.main()
