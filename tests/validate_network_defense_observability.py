#!/usr/bin/env python3
"""Run Network Defense observability validation in repository CI."""

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
TEST_FILES = (
    ROOT / "tests" / "test_network_defense_exporter.py",
    ROOT / "tests" / "test_network_defense_console.py",
)

suite = unittest.TestSuite()
for index, path in enumerate(TEST_FILES):
    spec = importlib.util.spec_from_file_location(f"network_defense_test_{index}", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"Unable to load Network Defense test file: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(module))

if suite.countTestCases() == 0:
    raise SystemExit("No Network Defense tests were loaded")

result = unittest.TextTestRunner(verbosity=2).run(suite)
if not result.wasSuccessful():
    raise SystemExit(1)

print(f"Network Defense observability validation passed ({suite.countTestCases()} tests)")
