#!/usr/bin/env python3

"""
WW.CX Registry Rebuild

Runs the complete registry import pipeline.
"""

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


STEPS = [
    "validate_registry.py",
    "import_countries.py",
    "import_calling_codes.py",
    "import_timezones.py",
    "import_nanpa.py",
    "refresh_sources.py",
]


for step in STEPS:

    path = ROOT / "tools" / "registry" / step

    if not path.exists():
        print(f"Missing: {path}")
        sys.exit(1)

    print()
    print("=" * 60)
    print(step)
    print("=" * 60)

    result = subprocess.run(
        ["python3", str(path)],
        cwd=ROOT
    )

    if result.returncode != 0:
        print(f"FAILED: {step}")
        sys.exit(result.returncode)


print()
print("Registry rebuild complete")
