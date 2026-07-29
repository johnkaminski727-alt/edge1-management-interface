#!/usr/bin/env python3
"""Run DNS Defense integration tests in repository CI."""

import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
TEST_FILE = ROOT / 'tests' / 'test_network_defense_dns_exporter.py'
SPEC = importlib.util.spec_from_file_location('network_defense_dns_tests', TEST_FILE)
if SPEC is None or SPEC.loader is None:
    raise SystemExit(f'Unable to load test file: {TEST_FILE}')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
SUITE = unittest.defaultTestLoader.loadTestsFromModule(MODULE)
if SUITE.countTestCases() == 0:
    raise SystemExit('No DNS integration tests were loaded')
RESULT = unittest.TextTestRunner(verbosity=2).run(SUITE)
if not RESULT.wasSuccessful():
    raise SystemExit(1)
print(f'DNS Network Defense validation passed ({SUITE.countTestCases()} tests)')
