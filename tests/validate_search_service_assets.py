#!/usr/bin/env python3
"""Validate the systemd service assets for the Private Library Search wrapper.

Repo-side checks only: no root, no systemd, no network. Safe to run anywhere.
"""

from __future__ import annotations

import configparser
import os
import stat
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UNIT = ROOT / "deploy" / "systemd" / "edge1-private-library-search.service"
INSTALLER = ROOT / "deploy" / "install-private-library-search-service.sh"
SMOKE = ROOT / "deploy" / "private-library-search-service-smoke-test.sh"
RUNBOOK = ROOT / "docs" / "handoff" / "private-library-search-service-runbook.md"
RUN_SCRIPT = ROOT / "bin" / "run_private_library_search.sh"


def assert_exists(path: Path) -> None:
    if not path.is_file():
        raise AssertionError(f"missing file: {path.relative_to(ROOT)}")


def assert_executable(path: Path) -> None:
    assert_exists(path)
    mode = path.stat().st_mode
    if not mode & stat.S_IXUSR:
        raise AssertionError(f"not executable: {path.relative_to(ROOT)}")


def parse_unit(path: Path) -> configparser.ConfigParser:
    parser = configparser.ConfigParser(strict=False)
    parser.optionxform = str  # preserve key case
    parser.read_string(path.read_text(encoding="utf-8"))
    return parser


def main() -> None:
    for path in (UNIT, INSTALLER, SMOKE, RUNBOOK, RUN_SCRIPT):
        assert_exists(path)
    for path in (INSTALLER, SMOKE, RUN_SCRIPT):
        assert_executable(path)

    unit = parse_unit(UNIT)

    for section in ("Unit", "Service", "Install"):
        if section not in unit:
            raise AssertionError(f"unit file missing [{section}] section")

    service = unit["Service"]

    exec_start = service.get("ExecStart", "")
    if "run_private_library_search.sh" not in exec_start:
        raise AssertionError("ExecStart must launch bin/run_private_library_search.sh")

    exec_path = exec_start.split()[0]
    relative = os.path.relpath(exec_path, "/opt/edge1-management-interface")
    if relative.startswith(".."):
        raise AssertionError("ExecStart must live under /opt/edge1-management-interface")
    if not (ROOT / relative).is_file():
        raise AssertionError(f"ExecStart target not present in repo: {relative}")

    # Localhost-only guardrails must stay in place.
    if service.get("IPAddressDeny", "").strip().lower() != "any":
        raise AssertionError("unit must set IPAddressDeny=any")
    if service.get("IPAddressAllow", "").strip().lower() != "localhost":
        raise AssertionError("unit must set IPAddressAllow=localhost")
    if service.get("NoNewPrivileges", "").strip().lower() != "true":
        raise AssertionError("unit must set NoNewPrivileges=true")

    # ProtectSystem must be full (not strict) to preserve library DB access;
    # see the runbook before changing this check.
    if service.get("ProtectSystem", "").strip().lower() != "full":
        raise AssertionError("unit must set ProtectSystem=full")

    # Installer must target the expected unit destination and refuse non-root.
    installer_text = INSTALLER.read_text(encoding="utf-8")
    for needle in (
        "/etc/systemd/system/edge1-private-library-search.service",
        "systemctl daemon-reload",
        "must run as root",
    ):
        if needle not in installer_text:
            raise AssertionError(f"installer missing expected content: {needle!r}")

    # Smoke test must probe the search API and the disallowed-collection guard.
    smoke_text = SMOKE.read_text(encoding="utf-8")
    for needle in (
        "/api/private-library/search",
        "collection=public",
        "edge1-private-library-search.service",
    ):
        if needle not in smoke_text:
            raise AssertionError(f"smoke test missing expected content: {needle!r}")

    print("search service asset validation passed")


if __name__ == "__main__":
    main()
