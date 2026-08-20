from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).parents[1]
SERVER = ROOT / "server"
if str(SERVER) not in sys.path:
    sys.path.insert(0, str(SERVER))


def load_module(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


producer = load_module("asterisk_readonly_snapshot", SERVER / "asterisk_readonly_snapshot.py")
consumer = load_module("asterisk_operator_diagnostics", SERVER / "asterisk_operator_diagnostics.py")

EXPECTED_IDS = (
    "asterisk.core_uptime",
    "asterisk.core_channels",
    "asterisk.pjsip_endpoints",
    "asterisk.pjsip_transports",
    "asterisk.pjsip_registrations",
    "asterisk.modules",
    "asterisk.http_status",
)


class AsteriskOperatorDiagnosticsTests(unittest.TestCase):
    def test_producer_has_exact_fixed_read_only_command_contract(self):
        ids = tuple(f"asterisk.{name}" for name, _argv in producer.COMMANDS)
        self.assertEqual(ids, EXPECTED_IDS)
        for _name, argv in producer.COMMANDS:
            self.assertEqual(argv[:2], ("asterisk", "-rx"))
            self.assertNotIn(argv[0], {"sudo", "su", "doas", "sh", "bash"})
        source = (SERVER / "asterisk_readonly_snapshot.py").read_text(encoding="utf-8")
        self.assertNotIn("argparse", source)
        self.assertNotIn("sys.argv", source)

    def test_producer_snapshot_records_only_fixed_successful_checks(self):
        result = {
            "available": True,
            "status": "ok",
            "exit_code": 0,
            "duration_ms": 1,
            "stdout": "ok\n",
            "stderr": "",
        }
        with mock.patch.object(producer, "run_fixed", return_value=result):
            snapshot = producer.build_snapshot()
        self.assertEqual(snapshot["contract"], "wwcx.edge1-asterisk-readonly-snapshot.v1")
        self.assertTrue(snapshot["read_only"])
        self.assertFalse(snapshot["parameters_accepted"])
        self.assertEqual(tuple(snapshot["command_ids"]), EXPECTED_IDS)
        self.assertEqual(snapshot["status"], "ok")
        self.assertEqual(tuple(item["argv_id"] for item in snapshot["checks"]), EXPECTED_IDS)

    def write_snapshot(self, path: pathlib.Path, *, generated_at: float, status: str = "ok"):
        checks = [
            {
                "name": command_id.split(".", 1)[1],
                "argv_id": command_id,
                "available": True,
                "status": "ok",
                "exit_code": 0,
                "duration_ms": 1,
                "stdout": "ok\n",
                "stderr": "",
            }
            for command_id in EXPECTED_IDS
        ]
        value = {
            "contract": consumer.SNAPSHOT_CONTRACT,
            "generated_at": "2026-08-20T04:34:00Z",
            "generated_at_epoch": generated_at,
            "read_only": True,
            "parameters_accepted": False,
            "command_ids": list(EXPECTED_IDS),
            "status": status,
            "checks": checks,
        }
        path.write_text(json.dumps(value), encoding="utf-8")
        os.chmod(path, 0o640)

    def test_consumer_accepts_fresh_owned_bounded_snapshot(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = pathlib.Path(temporary) / "status.json"
            self.write_snapshot(path, generated_at=1000.0)
            with mock.patch.object(
                consumer,
                "expected_snapshot_identity",
                return_value=(os.getuid(), os.getgid()),
            ):
                value, reason = consumer.load_native_snapshot(path, now=1010.0)
        self.assertIsNone(reason)
        self.assertEqual(value["status"], "ok")
        self.assertEqual(value["native_cli_status"], "ok")
        self.assertEqual(value["native_diagnostic_source"], "asterisk-owned-fixed-snapshot")
        self.assertEqual(value["snapshot"]["age_seconds"], 10)

    def test_consumer_fails_closed_on_stale_or_contract_drift(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = pathlib.Path(temporary) / "status.json"
            self.write_snapshot(path, generated_at=1000.0)
            with mock.patch.object(
                consumer,
                "expected_snapshot_identity",
                return_value=(os.getuid(), os.getgid()),
            ):
                value, reason = consumer.load_native_snapshot(path, now=1200.0)
                self.assertIsNone(value)
                self.assertEqual(reason, "snapshot_stale")

                data = json.loads(path.read_text(encoding="utf-8"))
                data["command_ids"][-1] = "asterisk.forbidden"
                path.write_text(json.dumps(data), encoding="utf-8")
                os.chmod(path, 0o640)
                value, reason = consumer.load_native_snapshot(path, now=1010.0)
                self.assertIsNone(value)
                self.assertEqual(reason, "snapshot_command_contract_drift")

    def test_consumer_preserves_existing_passive_fallback(self):
        fallback = {
            "component": "asterisk",
            "status": "limited",
            "native_cli_status": "error",
            "read_only": True,
            "checks": [],
            "passive_fallback": {"status": "ok"},
        }
        with mock.patch.object(consumer, "load_native_snapshot", return_value=(None, "snapshot_stale")), mock.patch.object(
            consumer.base, "component", return_value=fallback.copy()
        ):
            value = consumer.diagnostics()
        self.assertEqual(value["status"], "limited")
        self.assertEqual(value["passive_fallback"]["status"], "ok")
        self.assertEqual(value["bounded_snapshot_status"], "snapshot_stale")

    def test_systemd_helper_isolated_from_operations_api_principal(self):
        service = (ROOT / "deploy/systemd/edge1-asterisk-readonly-snapshot.service").read_text(encoding="utf-8")
        timer = (ROOT / "deploy/systemd/edge1-asterisk-readonly-snapshot.timer").read_text(encoding="utf-8")
        self.assertIn("User=asterisk", service)
        self.assertIn("Group=bigbird-audit", service)
        self.assertNotIn("User=wwadmin", service)
        self.assertNotIn("SupplementaryGroups=asterisk", service)
        self.assertIn("NoNewPrivileges=true", service)
        self.assertIn("RestrictAddressFamilies=AF_UNIX", service)
        self.assertIn("CapabilityBoundingSet=\n", service)
        self.assertIn("AmbientCapabilities=\n", service)
        self.assertNotIn("sudo", service)
        self.assertIn("RuntimeDirectoryMode=0750", service)
        self.assertIn("RuntimeDirectoryPreserve=yes", service)
        self.assertIn("OnUnitActiveSec=15s", timer)


if __name__ == "__main__":
    unittest.main()
