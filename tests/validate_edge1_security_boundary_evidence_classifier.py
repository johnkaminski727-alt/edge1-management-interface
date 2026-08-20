#!/usr/bin/env python3
"""Run the Edge1 security-boundary evidence-classifier regression suite."""

import unittest

from test_edge1_security_boundary_evidence_classifier import (
    SecurityBoundaryEvidenceClassifierTests,
)


suite = unittest.defaultTestLoader.loadTestsFromTestCase(
    SecurityBoundaryEvidenceClassifierTests
)
result = unittest.TextTestRunner(verbosity=2).run(suite)
if not result.wasSuccessful():
    raise SystemExit(1)
print("edge1 security-boundary evidence classifier validation passed")
