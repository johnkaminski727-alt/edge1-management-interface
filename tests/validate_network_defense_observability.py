#!/usr/bin/env python3
"""Run Network Defense observability validation in repository CI."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"

suite = unittest.defaultTestLoader.discover(
    start_dir=str(TESTS),
    pattern="test_network_defense_*.py",
    top_level_dir=str(ROOT),
)

if suite.countTestCases() == 0:
    raise SystemExit("No Network Defense tests were discovered")

result = unittest.TextTestRunner(verbosity=2).run(suite)
if not result.wasSuccessful():
    raise SystemExit(1)

print(f"Network Defense observability validation passed ({suite.countTestCases()} tests)")
