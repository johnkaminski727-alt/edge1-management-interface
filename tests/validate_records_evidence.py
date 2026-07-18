#!/usr/bin/env python3
"""Validate records-governance assets and their CI wiring."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "docs" / "records-governance" / "RECORDS_EVIDENCE_POLICY.md"
EVIDENCE_MAP = ROOT / "docs" / "records-governance" / "EVIDENCE_MAP.md"
WORKFLOW = ROOT / ".github" / "workflows" / "repository-validation.yml"


def require_file(path: Path) -> str:
    if not path.is_file():
        raise AssertionError(f"missing evidence asset: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def require_all(text: str, values: tuple[str, ...], label: str) -> None:
    missing = [value for value in values if value not in text]
    if missing:
        raise AssertionError(f"{label} missing required content: {missing}")


def main() -> int:
    for relative in (
        "README.md",
        "SECURITY.md",
        "CONTRIBUTING.md",
        "ROADMAP.md",
        "CITATION.cff",
    ):
        require_file(ROOT / relative)

    policy = require_file(POLICY)
    require_all(
        policy,
        (
            "## Status and purpose",
            "## Scope",
            "## Evidence principles",
            "## Minimum record metadata",
            "## Lifecycle",
            "## Integrity and security controls",
            "does not claim certification",
            "Data minimization",
            "Correct or supersede",
        ),
        "records policy",
    )

    evidence_map = require_file(EVIDENCE_MAP)
    require_all(
        evidence_map,
        (
            "# Repository Evidence Map",
            "## Evidence quality checklist",
            "## Current automated baseline",
            "CITATION.cff",
            "SECURITY.md",
            "CONTRIBUTING.md",
            "ROADMAP.md",
            "tests/validate_time_authority.py",
        ),
        "evidence map",
    )

    workflow = require_file(WORKFLOW)
    require_all(
        workflow,
        (
            "permissions:",
            "contents: read",
            "python3 tests/validate_static_ui.py",
            "python3 tests/validate_search_service_assets.py",
            "python3 tests/validate_time_authority.py",
            "python3 tests/validate_records_evidence.py",
            "workflow_dispatch:",
        ),
        "repository validation workflow",
    )

    print("records evidence validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
