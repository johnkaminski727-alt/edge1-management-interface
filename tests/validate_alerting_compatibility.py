#!/usr/bin/env python3
"""Run the bounded EBS and CAP-CP compatibility test suite in repository CI."""
from __future__ import annotations

import subprocess
import sys


def main() -> int:
    result = subprocess.run(
        [sys.executable, "-m", "unittest", "-v", "tests/test_alerting_compatibility.py"],
        check=False,
    )
    if result.returncode == 0:
        print("Alerting compatibility validation passed (9 tests)")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
