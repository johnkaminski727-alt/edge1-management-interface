#!/usr/bin/env python3
import importlib.util
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "cx_admin" / "discover_navigation.py"
SPEC = importlib.util.spec_from_file_location("discover_navigation", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class NavigationDiscoveryTests(unittest.TestCase):
    def test_inventory_uses_real_route(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            page = root / "bigbird-operations-console.php"
            page.write_text("<html><title>BigBird Operations Console</title><body><main></main></body></html>", encoding="utf-8")
            record = MODULE.inspect_page(root, page, "/admin")
            self.assertEqual(record["route"], "/admin/bigbird-operations-console.php")
            self.assertEqual(record["title"], "BigBird Operations Console")
            self.assertTrue(record["navigable_candidate"])

    def test_api_is_not_navigation_candidate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            page = root / "api" / "status.php"
            page.parent.mkdir()
            page.write_text("<?php echo json_encode(['ok' => true]);", encoding="utf-8")
            record = MODULE.inspect_page(root, page, "/admin")
            self.assertFalse(record["navigable_candidate"])
            self.assertIn("excluded implementation directory", record["exclusion_reasons"])

    def test_bootstrap_is_not_navigation_candidate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            page = root / "bigbird-ops" / "bootstrap.php"
            page.parent.mkdir()
            page.write_text("<html><title>WW.CX Operations Center</title><body></body></html>", encoding="utf-8")
            record = MODULE.inspect_page(root, page, "/admin")
            self.assertFalse(record["navigable_candidate"])
            self.assertIn("excluded implementation filename", record["exclusion_reasons"])

    def test_private_renderer_is_not_navigation_candidate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            page = root / "bigbird-ops-g1-v020" / "_private" / "src" / "renderers.php"
            page.parent.mkdir(parents=True)
            page.write_text("<html><title>Edge1 Operations Center</title><body></body></html>", encoding="utf-8")
            record = MODULE.inspect_page(root, page, "/admin")
            self.assertFalse(record["navigable_candidate"])
            self.assertIn("excluded implementation filename", record["exclusion_reasons"])
            self.assertIn("excluded implementation directory", record["exclusion_reasons"])

    def test_payload_tree_is_not_navigation_candidate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            page = root / "Project-Big-Bird-V4.0.7-Observability-R1" / "wwcx" / "payload" / "bigbird-firewall.php"
            page.parent.mkdir(parents=True)
            page.write_text("<html><body><main>Firewall</main></body></html>", encoding="utf-8")
            record = MODULE.inspect_page(root, page, "/admin")
            self.assertFalse(record["navigable_candidate"])
            self.assertIn("excluded implementation directory", record["exclusion_reasons"])


if __name__ == "__main__":
    unittest.main()
