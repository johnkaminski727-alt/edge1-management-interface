import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path("server/bigbird_edge1_connector.py")
SPEC = importlib.util.spec_from_file_location("bigbird_edge1_connector", MODULE_PATH)
CONNECTOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONNECTOR)


class BigBirdEdge1ConnectorTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.state_dir = self.root / "state"
        self.config_path = self.root / "connector.json"
        self.config = json.loads(Path("config/bigbird-edge1-connector.json").read_text())
        self.config_path.write_text(json.dumps(self.config), encoding="utf-8")

        self.originals = {
            "CONFIG": CONNECTOR.CONFIG,
            "STATE_DIR": CONNECTOR.STATE_DIR,
            "STATE": CONNECTOR.STATE,
            "AUDIT": CONNECTOR.AUDIT,
        }
        CONNECTOR.CONFIG = self.config_path
        CONNECTOR.STATE_DIR = self.state_dir
        CONNECTOR.STATE = self.state_dir / "restart-state.json"
        CONNECTOR.AUDIT = self.state_dir / "audit.jsonl"

    def tearDown(self):
        for name, value in self.originals.items():
            setattr(CONNECTOR, name, value)
        self.tempdir.cleanup()

    def test_policy_is_read_only(self):
        self.assertEqual(self.config["mode"], "read_only")
        self.assertIn("edge1.numbering.health", self.config["enabled_tools"])
        self.assertIn("edge1.repository.fetch", self.config["disabled_tools"])

    def test_restart_policy(self):
        policy = self.config["restart_policy"]
        self.assertEqual(policy["initial_interval_minutes"], 360)
        self.assertEqual(policy["increment_minutes"], 10)
        self.assertEqual(policy["maximum_interval_minutes"], 720)

    def test_validate_accepts_safe_configuration(self):
        result = CONNECTOR.validate()
        self.assertEqual(result["status"], "valid")
        self.assertEqual(result["mode"], "read_only")

    def test_successful_refresh_persists_state_and_audit(self):
        advertised = sorted(self.config["enabled_tools"])
        health = {"status": "ok", "mutations_enabled": False}
        with patch.object(CONNECTOR, "discover", return_value=(health, advertised, advertised, [])):
            result = CONNECTOR.refresh(force=True)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["state"]["restart_count"], 1)
        self.assertEqual(result["state"]["interval_minutes"], 370)
        self.assertIsNone(result["state"]["last_error"])

        persisted = json.loads(CONNECTOR.STATE.read_text(encoding="utf-8"))
        self.assertEqual(persisted["approved_actions"], advertised)
        events = [json.loads(line)["event"] for line in CONNECTOR.AUDIT.read_text().splitlines()]
        self.assertEqual(events, ["refresh_started", "refresh_succeeded"])

    def test_refresh_rejects_enabled_mutations(self):
        advertised = sorted(self.config["enabled_tools"])
        health = {"status": "ok", "mutations_enabled": True}
        with patch.object(CONNECTOR, "discover", return_value=(health, advertised, advertised, [])):
            with self.assertRaisesRegex(RuntimeError, "mutations must remain disabled"):
                CONNECTOR.refresh(force=True)

        persisted = json.loads(CONNECTOR.STATE.read_text(encoding="utf-8"))
        self.assertIn("mutations must remain disabled", persisted["last_error"])
        events = [json.loads(line)["event"] for line in CONNECTOR.AUDIT.read_text().splitlines()]
        self.assertEqual(events, ["refresh_started", "refresh_failed"])

    def test_refresh_skips_when_not_due(self):
        state = CONNECTOR.initial_state(self.config)
        state["next_due_at"] = "2999-01-01T00:00:00+00:00"
        CONNECTOR.atomic_write(CONNECTOR.STATE, state)
        with patch.object(CONNECTOR, "discover") as discover:
            result = CONNECTOR.refresh()
        self.assertEqual(result["status"], "not_due")
        discover.assert_not_called()


if __name__ == "__main__":
    unittest.main()
