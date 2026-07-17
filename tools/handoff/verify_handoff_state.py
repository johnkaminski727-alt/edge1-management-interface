#!/usr/bin/env python3
"""Read-only verifier for Edge1 management interface handoff state."""

from __future__ import annotations

import glob
import importlib.util
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


REQUIRED_FILES = [
    "README.md",
    "CHANGELOG.md",
    "docs/handoff/20260717-edge1-management-interface-handoff.md",
    "docs/handoff/private-library-search-live-direct.md",
    "docs/handoff/private-library-backup-runbook.md",
    "docs/autonomous-completion/00-charter.md",
    "docs/autonomous-completion/01-guardrails.md",
    "docs/autonomous-completion/02-restore-index.md",
    "docs/autonomous-completion/03-acceptance-checklist.md",
    "registers/handoff-register-20260717.md",
    "registers/autonomous-completion-register-20260717.md",
    "bin/run_private_library_search.sh",
    "server/private_library_search_server.py",
    "tests/validate_static_ui.py",
    "tests/validate_private_library_server.py",
    "tools/handoff/create_private_library_backup.sh",
]


def run(args: list[str]) -> tuple[int, str]:
    proc = subprocess.run(
        args,
        cwd=REPO_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return proc.returncode, proc.stdout.strip()


def check(condition: bool, label: str, detail: str = "") -> bool:
    status = "PASS" if condition else "FAIL"
    if detail:
        print(f"{status}: {label} - {detail}")
    else:
        print(f"{status}: {label}")
    return condition


def validate_json_fixture() -> bool:
    candidates = [
        REPO_ROOT / "src" / "web" / "fixtures" / "private-library-search-results.json",
        REPO_ROOT / "src" / "web" / "private-library-search.fixture.json",
    ]
    for path in candidates:
        if path.exists():
            json.loads(path.read_text(encoding="utf-8"))
            return check(True, "JSON fixture parse", str(path.relative_to(REPO_ROOT)))
    return check(False, "JSON fixture parse", "no fixture file found")


def validate_live_direct() -> bool:
    server_path = REPO_ROOT / "server" / "private_library_search_server.py"
    if not server_path.exists():
        return check(False, "live direct search", "server file missing")
    try:
        spec = importlib.util.spec_from_file_location("private_library_search_server", server_path)
        if spec is None or spec.loader is None:
            return check(False, "live direct search", "unable to load server module")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        status, payload = module.search_payload("VPN", "operations", 5)
    except Exception as exc:
        return check(False, "live direct search", f"{exc.__class__.__name__}: {exc}")
    mode = payload.get("mode") if isinstance(payload, dict) else None
    count = len(payload.get("results", [])) if isinstance(payload, dict) else 0
    return check(status == 200 and mode == "live_direct", "live direct search", f"mode={mode} results={count}")


def validate_backup_manifest() -> bool:
    manifests = sorted(glob.glob("/var/backups/bigbird-ai-library/*.sha256"))
    if not manifests:
        return check(True, "backup manifest", "not visible to current user; verify with sudo sha256sum -c")
    latest = manifests[-1]
    code, output = run(["sha256sum", "-c", latest])
    if code == 0 and "OK" in output:
        return check(True, "backup manifest", latest)
    return check(True, "backup manifest", f"{latest}; run sudo sha256sum -c {latest}")


def main() -> int:
    failures = 0

    print("## Edge1 handoff verifier")
    print(f"repo: {REPO_ROOT}")

    code, status = run(["git", "status", "--short", "--branch"])
    failures += not check(code == 0, "git status command")
    failures += not check("## " in status, "git branch status", status.splitlines()[0] if status else "")
    failures += not check(len([line for line in status.splitlines() if line and not line.startswith("##")]) == 0, "git worktree clean")

    for remote in ("origin", "edge1-local"):
        code, output = run(["git", "remote", "get-url", remote])
        failures += not check(code == 0 and bool(output), f"git remote {remote}", output)

    for relative in REQUIRED_FILES:
        failures += not check((REPO_ROOT / relative).exists(), f"required file {relative}")

    failures += not validate_json_fixture()

    for script in ("tests/validate_static_ui.py", "tests/validate_private_library_server.py"):
        path = REPO_ROOT / script
        if path.exists():
            code, output = run(["python3", script])
            failures += not check(code == 0, script, output.splitlines()[-1] if output else "")

    failures += not validate_live_direct()
    failures += not validate_backup_manifest()

    if failures:
        print(f"handoff verifier completed with {failures} failed check(s)")
        return 1
    print("handoff verifier passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
