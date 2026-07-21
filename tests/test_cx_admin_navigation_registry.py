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
            [sys.executable, str(VALID