#!/usr/bin/env python3
"""Run Network Defense observability validation in repository CI."""

import unittest


TEST_MODULES = (
    "tests.test_network_defense_exporter",
    "tests.test_network_defense_console",
)


suite = unittest.defaultTestLoader.loadTestsFromNames(TEST_MODULES)
result = unittest.TextTestRunner(verbosity=2).run(suite)
if not result.wasSuccessful():
    raise SystemExit(1)

print("Network Defense observability validation passed")
