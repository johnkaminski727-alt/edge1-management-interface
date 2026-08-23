#!/usr/bin/env python3
from __future__ import annotations

import unittest

from test_asterisk_process_identity import AsteriskProcessIdentityTests
from test_edge1_operator_disabled_commissioning import DisabledCommissioningTests
from test_edge1_operator_privileged_broker_v1 import PrivilegedBrokerV1Tests

suite = unittest.TestSuite()
for case in (AsteriskProcessIdentityTests, DisabledCommissioningTests, PrivilegedBrokerV1Tests):
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(case))
result = unittest.TextTestRunner(verbosity=2).run(suite)
if not result.wasSuccessful():
    raise SystemExit(1)
print("Edge1 Operator disabled commissioning validation passed")
