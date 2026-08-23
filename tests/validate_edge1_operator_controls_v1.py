#!/usr/bin/env python3
from __future__ import annotations

import unittest

from test_edge1_operator_controls_v1 import OperatorControlsV1Tests

suite = unittest.defaultTestLoader.loadTestsFromTestCase(OperatorControlsV1Tests)
result = unittest.TextTestRunner(verbosity=2).run(suite)
if not result.wasSuccessful():
    raise SystemExit(1)
print("Edge1 Operator controls v1 validation passed")
