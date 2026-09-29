#!/usr/bin/env python3
"""Read-only Ava clean-install preflight for rebuilt Edge1.

This script does not modify services, files, databases, or configuration.
It reports install gates needed before Ava activation.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path("/opt/edge1-management-interface")
CANDIDATE_REF = "origin/agent/ava-clean-install-3g4-integrated-20260929"
GATEWAY_MAIN = Path("/opt/bigbird-ai-gateway/app/main.py")
LIBRARY_DB = Path("/var/lib/bigbird-ai-library/library.sqlite3")
CONTACT_DB = Path("/var/lib/edge1-phone-intelligence/phone-intelligence.sqlite")
OPS_SECRET = Path("/etc/edge1-operations-api.secret")

SERVICES = (
    "edge1-operations-api.service",
    "edge1-operations-private-web.service",
    "edge1-private-library-search.service",
    "bigbird-ai-gateway.service",
)

REQUIRED_REPO_FILES = (
    "server/ava_agent_controller.py",
    "server/ava_contacts_gateway.py",
    "server/unified_contacts.py",
    "server/phone_intelligence_gateway.py",
    "server/private_library_search_server.py",
    "tests/test_ava_agent_controller.py",
    "tests/test_ava_contacts_gateway.py",
    "tests/validate_private_library_server.py",
)


def run(*argv: str) -> tuple[int, str]:
    p = subprocess.run(argv, text=True, capture_output=True, check=False)
    return p.returncode, (p.stdout + p.stderr).strip()


def git_ref_has_file(ref: str, path: str) -> bool:
    code, _ = run("git", "-C", str(REPO), "cat-file", "-e", f"{ref}:{path}")
    return code == 0


def service_state(name: str) -> str:
    code, out = run("systemctl", "is-active", name)
    if code == 0:
        return out or "active"
    return out or "inactive"


def http_json(url: str) -> dict:
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            raw = response.read(1024 * 1024)
            return {
                "http_status": int(response.status),
                "json": json.loads(raw.decode("utf-8")),
            }
    except urllib.error.HTTPError as exc:
        raw = exc.read(1024 * 1024)
        try:
            body = json.loads(raw.decode("utf-8"))
        except Exception:
            body = {"error": "non_json_response"}
        return {"http_status": int(exc.code), "json": body}
    except Exception as exc:
        return {"error": exc.__class__.__name__}


def gateway_version() -> str | None:
    if not GATEWAY_MAIN.is_file():
        return None
    text = GATEWAY_MAIN.read_text(encoding="utf-8", errors="replace")
    match = re.search(r'^APP_VERSION\s*=\s*["\']([^"\']+)["\']', text, re.M)
    return match.group(1) if match else "unknown"


def listening(port: int) -> list[str]:
    code, out = run("ss", "-ltn", f"sport = :{port}")
    if code != 0:
        return []
    return [line.strip() for line in out.splitlines()[1:] if line.strip()]


def main() -> int:
    report: dict[str, object] = {
        "preflight": "ava-clean-install",
        "mode": "read-only",
        "repo": str(REPO),
        "checks": {},
    }
    checks: dict[str, object] = report["checks"]  # type: ignore[assignment]

    checks["repo_present"] = REPO.is_dir()
    checks["working_tree_files"] = {
        name: (REPO / name).is_file() for name in REQUIRED_REPO_FILES
    }
    checks["candidate_ref"] = CANDIDATE_REF
    checks["candidate_source_files"] = {}
    if REPO.is_dir():
        code, out = run("git", "-C", str(REPO), "rev-parse", "HEAD")
        checks["repo_head"] = out if code == 0 else None
        code, out = run("git", "-C", str(REPO), "status", "--porcelain")
        checks["repo_clean"] = code == 0 and out == ""
        checks["repo_status"] = out.splitlines() if code == 0 and out else []
        code, out = run("git", "-C", str(REPO), "rev-parse", CANDIDATE_REF)
        checks["candidate_head"] = out if code == 0 else None
        checks["candidate_source_files"] = {
            name: git_ref_has_file(CANDIDATE_REF, name)
            for name in REQUIRED_REPO_FILES
        }

    checks["services"] = {name: service_state(name) for name in SERVICES}
    checks["gateway_main_present"] = GATEWAY_MAIN.is_file()
    checks["gateway_version"] = gateway_version()
    checks["operations_secret_present"] = OPS_SECRET.is_file()
    checks["library_db_present"] = LIBRARY_DB.is_file()
    checks["contacts_db_present"] = CONTACT_DB.is_file()

    checks["listeners"] = {
        "8091_library": listening(8091),
        "8097_operations_api": listening(8097),
        "8098_private_web": listening(8098),
        "8102_mcp": listening(8102),
    }

    checks["operations_health"] = http_json("http://127.0.0.1:8097/healthz")
    checks["library_probe"] = http_json(
        "http://127.0.0.1:8091/api/private-library/search"
        "?q=Edge1&collection=operations&limit=1"
    )

    library_probe = checks["library_probe"]
    library_live = False
    if isinstance(library_probe, dict):
        body = library_probe.get("json")
        if isinstance(body, dict):
            library_live = body.get("mode") in {"live", "live_direct"}
    checks["library_live_evidence_mode"] = library_live

    blocking = []
    if not checks["repo_present"]:
        blocking.append("repository missing")
    candidate_files = checks.get("candidate_source_files")
    if not isinstance(candidate_files, dict) or not candidate_files or not all(candidate_files.values()):
        blocking.append("required candidate source files missing")
    if checks.get("repo_clean") is False:
        blocking.append("working tree has uncommitted changes; preserve them before install")
    if not checks["gateway_main_present"]:
        blocking.append("Big Bird gateway source/runtime missing")
    if not checks["operations_secret_present"]:
        blocking.append("Operations API service credential missing")
    if not checks["contacts_db_present"]:
        blocking.append("Unified Contacts database missing")
    if not checks["library_db_present"]:
        blocking.append("Private Library database missing")
    if not library_live:
        blocking.append("Private Library is not returning live evidence")

    report["blocking"] = blocking
    report["ready_for_install_changes"] = not blocking

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if not blocking else 2


if __name__ == "__main__":
    raise SystemExit(main())
