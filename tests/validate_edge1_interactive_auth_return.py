from __future__ import annotations

import unittest

import test_edge1_interactive_auth_return


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromModule(test_edge1_interactive_auth_return)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
