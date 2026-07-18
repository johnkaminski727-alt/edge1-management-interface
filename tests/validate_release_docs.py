#!/usr/bin/env python3
"""Validate the controlled release documentation package.

Ensures every document referenced from docs/release/README.md's controlled
documents table exists, and that the required set is complete. Repo-side
only: no network, no root.
"""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RELEASE_DIR = ROOT / "docs" / "release"
INDEX = RELEASE_DIR / "README.md"

REQUIRED = {
    "release-checklist.md",
    "rollback-procedure.md",
    "release-evidence.md",
    "artifact-retention.md",
    "security-release-policy.md",
    "provenance-and-preservation.md",
    "release-notes-template.md",
}


def main() -> None:
    if not INDEX.is_file():
        raise AssertionError("docs/release/README.md is missing")

    text = INDEX.read_text(encoding="utf-8")

    # Every relative markdown link in the index must resolve.
    for link in re.findall(r"\]\(([^)]+\.md)\)", text):
        if link.startswith("http"):
            continue
        target = (RELEASE_DIR / link).resolve()
        if not target.is_file():
            raise AssertionError(f"release index links to missing file: {link}")

    # The required controlled set must exist on disk and be referenced.
    for name in sorted(REQUIRED):
        if not (RELEASE_DIR / name).is_file():
            raise AssertionError(f"missing controlled release document: {name}")
        if name not in text:
            raise AssertionError(f"release index does not reference: {name}")

    print("release documentation validation passed")


if __name__ == "__main__":
    main()
