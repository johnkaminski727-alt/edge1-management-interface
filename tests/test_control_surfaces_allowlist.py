import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).parents[1]


class ControlSurfaceAllowlistTests(unittest.TestCase):
    def test_control_surface_actions_are_fixed_and_read_only(self):
        data = json.loads((ROOT / "config" / "edge1-operations-allowlist.json").read_text())
        actions = data["actions"]
        expected = {
            "control_surfaces.summary": ["python3", "server/control_surface_diagnostics.py", "summary"],
            "control_surfaces.listeners": ["python3", "server/control_surface_diagnostics.py", "listeners"],
            "asterisk.diagnostics": ["python3", "server/asterisk_operator_diagnostics.py"],
            "kamailio.diagnostics": ["python3", "server/control_surface_diagnostics.py", "kamailio"],
            "freepbx.diagnostics": ["python3", "server/control_surface_diagnostics.py", "freepbx"],
        }
        for name, argv in expected.items():
            with self.subTest(action=name):
                action = actions[name]
                self.assertFalse(action["mutating"])
                self.assertEqual(action["argv"], argv)
                self.assertLessEqual(action["timeout_seconds"], 120)

    def test_no_control_surface_action_accepts_external_targets(self):
        data = json.loads((ROOT / "config" / "edge1-operations-allowlist.json").read_text())
        for name, action in data["actions"].items():
            if name.startswith("control_surfaces.") or name.endswith(".diagnostics"):
                text = " ".join(action["argv"])
                self.assertNotIn("http://", text)
                self.assertNotIn("https://", text)
                self.assertNotIn("--command", text)
                self.assertNotIn("--host", text)
                self.assertNotIn("--port", text)
                self.assertNotIn("sudo", text)

    def test_commissioning_security_assets_are_covered_by_config_digest(self):
        data = json.loads((ROOT / "config" / "edge1-operations-allowlist.json").read_text())
        argv = data["actions"]["config.digest"]["argv"]
        for path in (
            "server/edge1_operator_mcp_protocol.py",
            "server/edge1_operator_entrypoint.py",
            "server/asterisk_readonly_snapshot.py",
            "server/asterisk_operator_diagnostics.py",
            "deploy/systemd/edge1-asterisk-readonly-snapshot.service",
            "deploy/systemd/edge1-asterisk-readonly-snapshot.timer",
        ):
            self.assertIn(path, argv)


if __name__ == "__main__":
    unittest.main()
