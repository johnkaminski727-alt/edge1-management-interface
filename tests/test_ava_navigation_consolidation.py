import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "config" / "edge1_operator" / "navigation_registry.json"
LAUNCHER = ROOT / "src" / "web" / "edge1-ops" / "ava" / "index.html"


class AvaNavigationConsolidationTests(unittest.TestCase):
    def setUp(self):
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        self.by_id = {item["id"]: item for item in data["modules"]}

    def test_ava_is_single_visible_ai_identity(self):
        ava = self.by_id["ava-agent"]
        legacy = self.by_id["wwcx-ai"]

        self.assertEqual(ava["browser_route"], "/edge1-ops/status/ava/")
        self.assertEqual(ava["availability"], "accepted_live")
        self.assertEqual(ava["menu_visibility"], "live")
        self.assertTrue(ava["dashboard_visibility"])

        self.assertEqual(legacy["menu_visibility"], "hidden")
        self.assertFalse(legacy["dashboard_visibility"])
        self.assertIsNone(legacy["browser_route"])

    def test_launcher_uses_canonical_ava_browser_application(self):
        text = LAUNCHER.read_text(encoding="utf-8")

        self.assertIn("https://ww.cx/admin/ai/", text)
        self.assertIn(
            '/edge1-status/operator-shell/shell.css',
            text,
        )
        self.assertNotIn("http://", text)

    def test_registry_keeps_external_url_out_of_browser_route(self):
        for module in self.by_id.values():
            route = module.get("browser_route")
            if route:
                self.assertTrue(route.startswith("/"))
                self.assertNotIn("://", route)


if __name__ == "__main__":
    unittest.main()
