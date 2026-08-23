#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from test_edge1_operator_privileged_broker_v1 import PrivilegedBrokerV1Tests

suite = unittest.defaultTestLoader.loadTestsFromTestCase(PrivilegedBrokerV1Tests)
result = unittest.TextTestRunner(verbosity=2).run(suite)
if not result.wasSuccessful():
    raise SystemExit(1)
print("Edge1 Operator privileged broker v1 validation passed")
