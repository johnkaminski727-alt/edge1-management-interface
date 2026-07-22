import json
import unittest
from pathlib import Path


class BigBirdEdge1ConnectorTests(unittest.TestCase):
    def test_policy_is_read_only(self):
        cfg = json.loads(Path("config/bigbird-edge1-connector.json").read_text())
        self.assertEqual(cfg["mode"], "read_only")
        self.assertIn("edge1.numbering.health", cfg["enabled_tools"])
        self.assertIn("edge1.repository.fetch", cfg["disabled_tools"])

    def test_restart_policy(self):
        cfg = json.loads(Path("config/bigbird-edge1-connector.json").read_text())
        policy = cfg["restart_policy"]
        self.assertEqual(policy["initial_interval_minutes"], 360)
        self.assertEqual(policy["increment_minutes"], 10)
        self.assertEqual(policy["maximum_interval_minutes"], 720)


if __name__ == "__main__":
    unittest.main()
