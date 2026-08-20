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


if __name__ == "__main__":
    unittest.main()
