import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "config" / "edge1_operator" / "navigation_registry.json"
SCRIPT = ROOT / "src" / "web" / "operator-shell" / "shell.js"
STYLE = ROOT / "src" / "web" / "operator-shell" / "shell.css"


class Edge1OperatorShellTests(unittest.TestCase):
    def test_shell_assets_exist_and_are_navigation_only(self):
        script = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('event.key.toLowerCase() === "k"', script)
        self.assertIn("item.browser_route", script)
        self.assertNotIn("eval(", script)
        self.assertNotIn("Function(", script)
        self.assertNotIn("fetch(item", script)
        self.assertNotIn("POST", script)
        self.assertNotIn("PUT", script)
        self.assertNotIn("PATCH", script)
        self.assertNotIn("DELETE", script)

    def test_shell_fails_closed_on_safety_contract_and_keeps_escape(self):
        script = SCRIPT.read_text(encoding="utf-8")
        for marker in (
            "navigation_grants_authorization !== false",
            "generic_execution_authorized !== false",
            "production_traffic_authorized !== false",
            "mutations_enabled !== false",
            "unknown_status_is_healthy !== false",
        ):
            self.assertIn(marker, script)
        self.assertIn("Navigation unavailable · safety state unknown", script)
        self.assertIn('escape.href = "/edge1-status/"', script)

    def test_registry_has_no_external_browser_urls(self):
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        for module in data["modules"]:
            route = module.get("browser_route")
            if route:
                self.assertTrue(route.startswith("/"))
                self.assertNotIn("://", route)

    def test_responsive_and_accessible_hooks_exist(self):
        style = STYLE.read_text(encoding="utf-8")
        script = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("@media(max-width:900px)", style)
        self.assertIn("focus-visible", style)
        self.assertIn('aria-expanded', script)
        self.assertIn('aria-modal', script)
        self.assertIn('aria-current', script)
        self.assertIn('event.key === "Escape" && !drawer.hidden', script)


if __name__ == "__main__":
    unittest.main()
