#!/usr/bin/env python3

"""
WW.CX Full Registry Import Orchestrator
"""

import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone


ROOT = Path(__file__).resolve().parents[2]

STEPS = [
    "validate_registry.py",
    "import_countries.py",
    "import_calling_codes.py",
    "import_timezones.py",
    "import_nanpa.py",
    "refresh_sources.py",
]


def main():

    print(
        "WW.CX registry import started",
        datetime.now(timezone.utc).isoformat()
    )

    for step in STEPS:

        print()
        print("=" * 60)
        print(step)
        print("=" * 60)

        result = subprocess.run(
            [
                "python3",
                str(ROOT / "tools/registry" / step)
            ],
            cwd=ROOT
        )

        if result.returncode != 0:
            print("FAILED:", step)
            sys.exit(result.returncode)

    print()
    print("WW.CX registry import completed")


if __name__ == "__main__":
    main()
