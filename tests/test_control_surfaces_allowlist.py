import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).parents[1]


class ControlSurfaceAllowlistTests(unittest.TestCase):
    def test_control_surface_actions_are_fixed_and_read_only(self):
        data = json.loads((ROOT / "config" / "edge1-operations-allowlist.json").read_text())
        actions = data["actions"]
        expected = {
            "control_surfaces.summary": "summary",
            "control_surfaces.listeners": "listeners",
            "asterisk.diagnostics": "asterisk",
            "kamailio.diagnostics": "kamailio",
            "freepbx.diagnostics": "freepbx",
        }
        for name, profile in expected.items():
            with self.subTest(action=name):
                action = actions[name]
                self.assertFalse(action["mutating"])
                self.assertEqual(
                    action["argv"],
                    ["python3", "server/control_surface_diagnostics.py", profile],
                )
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


if __name__ == "__main__":
    unittest.main()
