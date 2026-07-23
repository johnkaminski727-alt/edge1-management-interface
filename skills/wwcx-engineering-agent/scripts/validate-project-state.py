#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REQUIRED_FILES = [
    ".agent/mission.md",
    ".agent/authority.md",
    ".agent/project-state.md",
    ".agent/decisions.md",
    ".agent/validation.md",
    ".agent/handoff.md",
]

REQUIRED_HEADINGS = {
    ".agent/project-state.md": ["Objective", "Current state", "Next actions", "Validation"],
    ".agent/validation.md": ["Validation"],
}

SECRET_PATTERNS = [
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----"),
    re.compile(r"(?i)\b(?:api[_-]?key|access[_-]?token|client[_-]?secret|password)\b\s*[:=]\s*[^\s<>{}\[\]]{8,}"),
]

PLACEHOLDERS = re.compile(r"(?i)\b(?:TODO|TBD|FIXME|CHANGEME|REPLACE_ME)\b")


def heading_present(text: str, heading: str) -> bool:
    return re.search(rf"(?im)^#{{1,6}}\s+{re.escape(heading)}\s*$", text) is not None


def validate(root: Path) -> list[str]:
    errors: list[str] = []

    for rel in REQUIRED_FILES:
        path = root / rel
        if not path.is_file():
            errors.append(f"missing required file: {rel}")
            continue

        text = path.read_text(encoding="utf-8", errors="replace")
        if not text.strip():
            errors.append(f"empty required file: {rel}")

        for heading in REQUIRED_HEADINGS.get(rel, []):
            if not heading_present(text, heading):
                errors.append(f"{rel}: missing heading '{heading}'")

        if PLACEHOLDERS.search(text):
            errors.append(f"{rel}: contains unresolved placeholder")

        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                errors.append(f"{rel}: possible secret detected")
                break

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate WW.CX .agent project-state files")
    parser.add_argument("root", nargs="?", default=".", help="project root")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    errors = validate(root)

    if errors:
        print("Project-state validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Project-state validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
