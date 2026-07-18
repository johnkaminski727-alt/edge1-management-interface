#!/usr/bin/env python3
"""Validate the operator tooling: validation entry point and health summary.

Repo-side only: exercises --list/--help paths and static requirements
without needing systemd, services, or network.
"""

from __future__ import annotations

import stat
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / "bin" / "validate-repo"
HEALTH = ROOT / "tools" / "operator" / "edge1-health-summary.py"


def assert_executable(path: Path) -> None:
    if not path.is_file():
        raise AssertionError(f"missing file: {path.relative_to(ROOT)}")
    if not path.stat().st_mode & stat.S_IXUSR:
        raise AssertionError(f"not executable: {path.relative_to(ROOT)}")


def main() -> None:
    assert_executable(ENTRY)
    assert_executable(HEALTH)

    listed = subprocess.run(
        [sys.executable, str(ENTRY), "--list"],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    if listed.returncode != 0:
        raise AssertionError("validate-repo --list failed")
    for step in ("validation tests", "python compileall", "shell syntax"):
        if step not in listed.stdout:
            raise AssertionError(f"validate-repo --list missing step: {step}")

    for script in (ENTRY, HEALTH):
        helped = subprocess.run(
            [sys.executable, str(script), "--help"],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        # --help exits 0 for argparse tools; the health tool has no argparse
        # flags, so accept a normal run being triggered instead is NOT okay —
        # ensure it at least compiles and does not crash on import.
        if script is ENTRY and helped.returncode != 0:
            raise AssertionError("validate-repo --help failed")

    compiled = subprocess.run(
        [sys.executable, "-m", "py_compile", str(ENTRY), str(HEALTH)],
        capture_output=True,
        text=True,
    )
    if compiled.returncode != 0:
        raise AssertionError(f"operator tools failed to compile: {compiled.stderr.strip()}")

    health_text = HEALTH.read_text(encoding="utf-8")
    for needle in ("127.0.0.1:8091", "127.0.0.1:8092", "read-only", "is-active"):
        if needle not in health_text:
            raise AssertionError(f"health summary missing expected content: {needle!r}")
    for forbidden in ("0.0.0.0", "password", "token"):
        if forbidden in health_text:
            raise AssertionError(f"health summary must not contain {forbidden!r}")

    print("operator tools validation passed")


if __name__ == "__main__":
    main()
