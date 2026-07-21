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
    def test_inventory_uses_real_relative_route_and_title(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            page = root / "bigbird-operations-console.php"
            page.write_text(
                "<html><head><title>BigBird Operations Console</title></head>"
                "<body><main><a href='telephony.php'>Telephony</a></main></body></html>",
                encoding="utf-8",
            )
            record = MODULE.inspect_page(root, page, "/admin")
            self.assertEqual(record["route"], "/admin/bigbird-operations-console.php")
            self.assertEqual(record["title"], "BigBird Operations Console")
            self.assertTrue(record["navigable_candidate"])
            self.assertEqual(record["outbound_links"], ["telephony.php"])

    def test_api_and_handler_paths_are_not_navigation_candidates(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            page = root / "api" / "status.php"
            page.parent.mkdir()
            page.write_text("<?php echo json_encode(['ok' => true]);", encoding="utf-8")
            record = MODULE.inspect_page(root, page, "/admin")
            self.assertFalse(record["navigable_candidate"])
            self.assertIn("excluded implementation directory", record["exclusion_reasons"])


if __name__ == "__main__":
    unittest.main()
