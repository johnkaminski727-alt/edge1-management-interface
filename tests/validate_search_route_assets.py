#!/usr/bin/env python3
"""Validate the approval-gated VPN route assets for Private Library Search.

Repo-side checks only: no root, no nginx, no network. Safe to run anywhere.
"""

from __future__ import annotations

import stat
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "deploy" / "nginx" / "edge1-private-library-search.conf.template"
INSTALLER = ROOT / "deploy" / "install-private-library-search-route.sh"
HTPASSWD_HELPER = ROOT / "deploy" / "create-search-route-htpasswd.sh"
SMOKE = ROOT / "deploy" / "private-library-search-route-smoke-test.sh"
RUNBOOK = ROOT / "docs" / "handoff" / "private-library-search-route-runbook.md"


def assert_exists(path: Path) -> None:
    if not path.is_file():
        raise AssertionError(f"missing file: {path.relative_to(ROOT)}")


def assert_executable(path: Path) -> None:
    assert_exists(path)
    if not path.stat().st_mode & stat.S_IXUSR:
        raise AssertionError(f"not executable: {path.relative_to(ROOT)}")


def main() -> None:
    for path in (TEMPLATE, INSTALLER, HTPASSWD_HELPER, SMOKE, RUNBOOK):
        assert_exists(path)
    for path in (INSTALLER, HTPASSWD_HELPER, SMOKE):
        assert_executable(path)

    template = TEMPLATE.read_text(encoding="utf-8")

    # The template must keep authentication and the read-only method guard.
    for needle in (
        "auth_basic",
        "auth_basic_user_file",
        "limit_except GET HEAD",
        "proxy_pass http://127.0.0.1:8091",
        "__VPN_BIND_IP__",
        "__ROUTE_PORT__",
    ):
        if needle not in template:
            raise AssertionError(f"nginx template missing expected content: {needle!r}")

    # The template must never carry an all-interfaces bind.
    for forbidden in ("0.0.0.0", "listen [::]", "listen *:"):
        if forbidden in template:
            raise AssertionError(f"nginx template must not contain {forbidden!r}")

    installer = INSTALLER.read_text(encoding="utf-8")

    # The approval gate must stay in place, in all four layers.
    for needle in (
        "--approve-route-exposure",
        "expose search route",
        "EDGE1_ROUTE_APPROVAL",
        "is_private",
        "is_unspecified",
        "must run as root",
        "nginx -t",
    ):
        if needle not in installer:
            raise AssertionError(f"route installer missing expected content: {needle!r}")

    smoke = SMOKE.read_text(encoding="utf-8")
    for needle in (
        "401",
        "/api/private-library/search",
        "sport = :8091",
        "0\\.0\\.0\\.0",
    ):
        if needle not in smoke:
            raise AssertionError(f"route smoke test missing expected content: {needle!r}")

    runbook = RUNBOOK.read_text(encoding="utf-8")
    if "PREPARED, NOT INSTALLED" not in runbook:
        raise AssertionError("runbook must state the prepared/not-installed status")

    print("search route asset validation passed")


if __name__ == "__main__":
    main()
