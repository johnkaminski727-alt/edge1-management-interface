#!/usr/bin/env python3
"""Regression tests for live inventory directory-prefix validation."""
from __future__ import annotations

import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "security" / "reconcile-edge1-live-inventory.py"

SPEC = importlib.util.spec_from_file_location("reconcile_edge1_live_inventory", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class LiveInventoryPrefixCompatibilityTests(unittest.TestCase):
    def test_valid_directory_prefixes_keep_required_trailing_slash(self) -> None:
        for value in ("security/", "network-defense/", "bitcoin/", "mining/", "reports/"):
            with self.subTest(value=value):
                self.assertEqual(MODULE.safe_relative_compat(value, directory=True), value)

    def test_exact_paths_and_unsafe_prefixes_remain_rejected(self) -> None:
        self.assertEqual(MODULE.safe_relative_compat("index.html"), "index.html")
        for value, directory in (
            ("security", True),
            ("security/", False),
            ("../security/", True),
            ("security//nested/", True),
            ("/security/", True),
            ("security/%2e%2e/", True),
        ):
            with self.subTest(value=value, directory=directory):
                with self.assertRaises(ValueError):
                    MODULE.safe_relative_compat(value, directory=directory)

    def test_committed_manifest_validates_through_compatibility_path(self) -> None:
        manifest = MODULE.load_object(MODULE.DEFAULT_MANIFEST)
        access_policy = MODULE.load_access_policy(MODULE.DEFAULT_ACCESS_POLICY)
        MODULE.artifact_manifest.safe_relative = MODULE.safe_relative_compat
        MODULE.artifact_manifest.validate_manifest(manifest, access_policy)


if __name__ == "__main__":
    unittest.main()
