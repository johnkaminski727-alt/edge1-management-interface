#!/usr/bin/env python3
"""Generate the canonical Edge1 Intelligence navigation."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path


START = "<!-- EDGE1_INTELLIGENCE_NAV_START -->"
END = "<!-- EDGE1_INTELLIGENCE_NAV_END -->"

ROOT = Path(__file__).resolve().parents[2]

MANIFEST = (
    ROOT
    / "src"
    / "web"
    / "shared"
    / "intelligence-nav.json"
)


def load_modules():
    data = json.loads(MANIFEST.read_text())
    modules = data.get("modules")

    if not isinstance(modules, list) or not modules:
        raise SystemExit("Navigation manifest is empty.")

    seen = set()

    for module in modules:
        for field in ("id", "label", "href"):
            if not module.get(field):
                raise SystemExit(
                    f"Missing {field}: {module!r}"
                )

        if module["id"] in seen:
            raise SystemExit(
                f"Duplicate module id: {module['id']}"
            )

        seen.add(module["id"])

    return modules


def active_module(text):
    marker = 'data-edge1-module="'
    start = text.find(marker)

    if start < 0:
        raise SystemExit(
            "Missing data-edge1-module."
        )

    start += len(marker)
    end = text.find('"', start)

    if end < 0:
        raise SystemExit(
            "Malformed data-edge1-module."
        )

    return text[start:end]


def render(modules, active):
    ids = {module["id"] for module in modules}

    if active not in ids:
        raise SystemExit(
            f"Unknown active module: {active}"
        )

    lines = [
        START,
        (
            '  <nav class="module-nav" '
            'aria-label="Edge1 modules">'
        ),
    ]

    for module in modules:
        label = html.escape(
            module["label"],
            quote=True,
        )

        href = html.escape(
            module["href"],
            quote=True,
        )

        current = (
            ' aria-current="page"'
            if module["id"] == active
            else ""
        )

        lines.append(
            f'    <a href="{href}"{current}>'
            f'{label}</a>'
        )

    lines.extend([
        "  </nav>",
        END,
    ])

    return "\n".join(lines)


def generate(path, check=False):
    text = path.read_text()

    if text.count(START) != 1:
        raise SystemExit(
            f"{path}: expected one START marker."
        )

    if text.count(END) != 1:
        raise SystemExit(
            f"{path}: expected one END marker."
        )

    active = active_module(text)

    generated = render(
        load_modules(),
        active,
    )

    start = text.index(START)
    end = text.index(END) + len(END)

    updated = (
        text[:start]
        + generated
        + text[end:]
    )

    if check:
        if updated != text:
            raise SystemExit(
                f"STALE GENERATED NAV: {path}"
            )

        print(
            f"PASS {path} active={active}"
        )

    elif updated != text:
        path.write_text(updated)

        print(
            f"UPDATED {path} active={active}"
        )

    else:
        print(
            f"UNCHANGED {path} active={active}"
        )


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--check",
        action="store_true",
    )

    parser.add_argument(
        "paths",
        nargs="+",
        type=Path,
    )

    args = parser.parse_args()

    for path in args.paths:
        generate(path, args.check)


if __name__ == "__main__":
    main()
