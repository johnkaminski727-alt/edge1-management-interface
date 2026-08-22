import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "config" / "edge1_operator" / "navigation_registry.json"
VALIDATOR = ROOT / "tools" / "edge1_operator" / "validate_navigation_registry.py"


class Edge1OperatorNavigationRegistryTests(unittest.TestCase):
    def test_registry_validation(self):
        result = subprocess.run(
            [sys.executable, str(VALIDATOR), str(REGISTRY)],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("accepted browser routes: 6", result.stdout)

    def test_palette_is_navigation_only(self):
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for module in data["modules"]:
            if module["palette"]:
                self.assertEqual(module["availability"], "accepted_live")
                self.assertTrue(module["browser_route"].startswith("/edge1-status/"))
                self.assertNotIn("command", module)
                self.assertNotIn("action", module)

    def test_unaccepted_surfaces_are_not_browser_routes(self):
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        by_id = {item["id"]: item for item in data["modules"]}
        self.assertIsNone(by_id["communications-workspace"]["browser_route"])
        self.assertIsNone(by_id["security-console"]["browser_route"])
        self.assertIsNone(by_id["wwcx-ai"]["browser_route"])
        self.assertIsNone(by_id["cookie-monster"]["browser_route"])

    def test_cookie_monster_is_registered_but_not_promoted(self):
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        by_id = {item["id"]: item for item in data["modules"]}
        module = by_id["cookie-monster"]
        self.assertEqual(module["candidate_route"], "/edge1-status/cookie-monster/")
        self.assertEqual(module["runtime_route"], "/edge1-status/cookie-monster/")
        self.assertEqual(module["availability"], "staged_disabled")
        self.assertEqual(module["authorization"], "unverified_route_policy")
        self.assertFalse(module["palette"])
        self.assertFalse(module["toolbox"])
        self.assertEqual(module["evidence_status"], "verified_repository_unaccepted_browser")


if __name__ == "__main__":
    unittest.main()
