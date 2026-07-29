#!/usr/bin/env python3
"""Repository CI entrypoint for staged DNS Defense policy foundation."""

import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
TEST_FILE = ROOT / "tests" / "test_dns_defense_policy.py"
SPEC = importlib.util.spec_from_file_location("dns_defense_policy_tests", TEST_FILE)
if SPEC is None or SPEC.loader is None:
    raise SystemExit(f"Unable to load DNS Defense test file: {TEST_FILE}")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
SUITE = unittest.defaultTestLoader.loadTestsFromModule(MODULE)
if SUITE.countTestCases() == 0:
    raise SystemExit("No DNS Defense tests were loaded")
RESULT = unittest.TextTestRunner(verbosity=2).run(SUITE)
if not RESULT.wasSuccessful():
    raise SystemExit(1)
print(f"DNS Defense policy validation passed ({SUITE.countTestCases()} tests)")
