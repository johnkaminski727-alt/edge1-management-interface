#!/usr/bin/env python3
"""CI entry point for public authority registry source validation."""

from pathlib import Path
import runpy


ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "tools" / "registry" / "validate_public_authority_sources.py"


if __name__ == "__main__":
    runpy.run_path(str(VALIDATOR), run_name="__main__")
