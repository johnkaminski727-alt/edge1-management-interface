"""Regression tests for the shared Edge1 Intelligence navigation."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

MANIFEST = (
    ROOT
    / "src"
    / "web"
    / "shared"
    / "intelligence-nav.json"
)

GENERATOR = (
    ROOT
    / "tools"
    / "web"
    / "generate_intelligence_nav.py"
)

PAGES = {
    "phone-directory": (
        ROOT
        / "src"
        / "web"
        / "phone-directory"
        / "index.html"
    ),
    "contacts": (
        ROOT
        / "src"
        / "web"
        / "contacts"
        / "index.html"
    ),
}


def manifest_modules():
    data = json.loads(MANIFEST.read_text())
    return data["modules"]


def test_manifest_is_valid():
    data = json.loads(MANIFEST.read_text())

    assert data["version"] == 2
    assert data["contract"] == "wwcx.edge1-application-registry.v1"
    assert data["navigation_grants_authorization"] is False

    modules = data["modules"]

    assert modules

    ids = [module["id"] for module in modules]
    labels = [module["label"] for module in modules]
    hrefs = [module["href"] for module in modules]

    assert len(ids) == len(set(ids))
    assert len(labels) == len(set(labels))
    assert len(hrefs) == len(set(hrefs))

    for module in modules:
        assert module["id"]
        assert module["label"]
        assert module["href"].startswith("/")
        assert module["section"]
        assert isinstance(module["sort_order"], int)
        assert module["required_scopes"]
        assert module["enabled"] is True

    assert modules == sorted(
        modules,
        key=lambda module: (module["sort_order"], module["id"]),
    )


def test_pages_are_generated_and_current():
    subprocess.run(
        [
            sys.executable,
            "-B",
            str(GENERATOR),
            "--check",
            *[
                str(path)
                for path in PAGES.values()
            ],
        ],
        cwd=ROOT,
        check=True,
    )


def test_every_page_has_every_module():
    modules = manifest_modules()

    for active_id, path in PAGES.items():
        text = path.read_text()

        assert (
            f'data-edge1-module="{active_id}"'
            in text
        )

        for module in modules:
            assert module["label"] in text
            assert (
                f'href="{module["href"]}"'
                in text
            )


def test_exactly_one_active_module_per_page():
    modules = manifest_modules()

    for active_id, path in PAGES.items():
        text = path.read_text()

        assert text.count(
            'aria-current="page"'
        ) == 1

        active = next(
            module
            for module in modules
            if module["id"] == active_id
        )

        expected = (
            f'href="{active["href"]}" '
            f'aria-current="page">'
            f'{active["label"]}</a>'
        )

        assert expected in text


def test_navigation_order_is_identical():
    modules = manifest_modules()

    expected_labels = [
        module["label"]
        for module in modules
    ]

    start_marker = (
        "<!-- EDGE1_INTELLIGENCE_NAV_START -->"
    )

    end_marker = (
        "<!-- EDGE1_INTELLIGENCE_NAV_END -->"
    )

    for path in PAGES.values():
        text = path.read_text()

        assert text.count(start_marker) == 1
        assert text.count(end_marker) == 1

        start = text.index(start_marker)
        end = (
            text.index(end_marker, start)
            + len(end_marker)
        )

        nav = text[start:end]

        positions = [
            nav.index(label)
            for label in expected_labels
        ]

        assert positions == sorted(positions)


def test_generated_navigation_contains_no_literal_escape_artifacts():
    for path in PAGES.values():
        text = path.read_text()
        start = text.index("<!-- EDGE1_INTELLIGENCE_NAV_START -->")
        end = text.index("<!-- EDGE1_INTELLIGENCE_NAV_END -->", start)
        nav = text[start:end]
        assert "\\n" not in nav
