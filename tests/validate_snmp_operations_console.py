#!/usr/bin/env python3
"""Run focused authenticated SNMP Operations Console unit/static regressions in CI."""
from __future__ import annotations

import unittest

from tests.test_edge1_snmp_ui_client import SnmpUiClientTests
from tests.test_snmp_operations_console import SnmpOperationsConsoleStaticTests


def main() -> int:
    suite = unittest.TestSuite()
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(SnmpUiClientTests))
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(SnmpOperationsConsoleStaticTests))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
