#!/usr/bin/env python3
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "tools" / "cx_admin" / "validate_navigation_registry.py"
REGISTRY = ROOT / "config" / "cx_admin" / "navigation_registry.json"


class NavigationRegistryTests(unittest.TestCase):
    def run_validator(self, *arguments):
        return subprocess.run(
            [sys.executable, str(VALIDATOR), str(REGISTRY)] + list(arguments),
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )

    def test_discovery_registry_is_structurally_valid(self):
        result = self.run_validator()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("verified routes: 13", result.stdout)
        self.assertIn("deployment status: blocked pending source metadata", result.stdout)

    def test_discovery_registry_is_not_menu_ready(self):
        result = self.run_validator("--require-menu-ready")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("menu metadata unresolved", result.stdout)


if __name__ == "__main__":
    unittest.main()
