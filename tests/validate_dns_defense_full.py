#!/usr/bin/env python3
"""Run all DNS Defense validation suites."""

import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
FILES = (
    ROOT / 'tests' / 'test_dns_defense_policy.py',
    ROOT / 'tests' / 'test_network_defense_dns_exporter.py',
)

suite = unittest.TestSuite()
for index, path in enumerate(FILES):
    spec = importlib.util.spec_from_file_location(f'dns_defense_suite_{index}', path)
    if spec is None or spec.loader is None:
        raise SystemExit(f'Unable to load {path}')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(module))

result = unittest.TextTestRunner(verbosity=2).run(suite)
if not result.wasSuccessful():
    raise SystemExit(1)

print(f'DNS Defense full validation passed ({suite.countTestCases()} tests)')
