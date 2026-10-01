#!/usr/bin/env python3
"""Validate the unified Edge1 frontend and exercise a NON-PRODUCTION publisher fixture.

The fixture rewrites three absolute paths and disables the root requirement in an
isolated COPY of the publisher. Never invokes the installed production publisher.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLISHER = ROOT / "deploy/operations-center/publish.sh"
EXPECTED = {
    "src/web/operations-center/index.html": "index.html",
    "src/web/operations-center/core-dashboard.js": "core-dashboard.js",
    "src/web/operations-center/crowdsec-dashboard.js": "crowdsec-dashboard.js",
    "src/web/security/index.html": "security/index.html",
    "src/web/security/correlation.html": "security/correlation.html",
    "src/web/security/crowdsec-dashboard.js": "security/crowdsec-dashboard.js",
    "src/web/network-defense/index.html": "network-defense/index.html",
    "src/web/operator-shell/shell.css": "operator-shell/shell.css",
    "src/web/operator-shell/theme.css": "operator-shell/theme.css",
    "src/web/operator-shell/shell.js": "operator-shell/shell.js",
    "config/edge1_operator/navigation_registry.json": "operator-shell/navigation.json",
}
ROUTES = {
    "operations-center": "/edge1-ops/status/",
    "security-operations": "/edge1-ops/status/security/",
    "security-correlation": "/edge1-ops/status/security/correlation.html",
    "network-defense": "/edge1-ops/status/network-defense/",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


class Page(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []
        self.links: list[str] = []
        self.scripts: list[dict[str, str]] = []
        self.styles: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = dict(attrs)
        if a.get("id"):
            self.ids.append(a["id"])
        if tag == "a" and a.get("href"):
            self.links.append(a["href"])
        if tag == "script":
            self.scripts.append({k: v or "" for k, v in a.items()})
        if tag == "link" and a.get("rel") == "stylesheet":
            self.styles.append(a.get("href", ""))


def validate_sources() -> None:
    publisher = PUBLISHER.read_text(encoding="utf-8")
    pairs = re.findall(r'^\s+"(src/[^"|]+|config/[^"|]+)\|([^"|]+)"\s*$', publisher, re.M)
    require(dict(pairs) == EXPECTED and len(pairs) == len(EXPECTED),
            "Publisher asset mapping differs from accepted contract")
    for source in EXPECTED:
        require((ROOT / source).is_file(), "Missing source: " + source)
    subprocess.run(["bash", "-n", str(PUBLISHER)], check=True)

    registry = json.loads(
        (ROOT / "config/edge1_operator/navigation_registry.json").read_text()
    )
    safety = registry.get("safety", {})
    require(safety and all(value is False for value in safety.values()),
            "Operator safety switches must remain false")
    live = {m["id"]: m for m in registry["modules"]
            if m.get("availability") == "accepted_live"}
    require(set(live) == set(ROUTES), "Live navigation must have exactly four modules")
    for mid, route in ROUTES.items():
        require(live[mid]["browser_route"] == route, "Unexpected route: " + mid)
    for m in registry["modules"]:
        if m["id"] not in ROUTES:
            require(not m.get("palette") and not m.get("toolbox"),
                    "Undeployed module exposed in live menu: " + m["id"])

    pages = {
        "operations-center": ROOT / "src/web/operations-center/index.html",
        "security-operations": ROOT / "src/web/security/index.html",
        "security-correlation": ROOT / "src/web/security/correlation.html",
        "network-defense": ROOT / "src/web/network-defense/index.html",
    }
    for mid, path in pages.items():
        html = path.read_text(encoding="utf-8")
        parsed = Page()
        parsed.feed(html)
        require(parsed.ids.count("wwcx-operator-shell") == 1, "Missing shell: " + mid)
        require(any(s.get("data-module") == mid for s in parsed.scripts),
                "Missing shell module binding: " + mid)
        require(any("operator-shell/shell.css" in s for s in parsed.styles),
                "Missing shared CSS: " + mid)
        for broken in ("/edge1-ops/status/bitcoin/", "/edge1-ops/status/mining/",
                       "/edge1-ops/status/daily-summary.html"):
            require(broken not in parsed.links, "Broken navigation: " + broken)
    main = pages["operations-center"].read_text()
    for marker in ("core-cards", "crowdsec-cards", "legacy-telemetry"):
        require(marker in main, "Missing Operations Center panel: " + marker)
    print("PASS: Four-page authenticated navigation and shared-theme source contract")


def test_publisher_fixture() -> None:
    original = PUBLISHER.read_text(encoding="utf-8")
    old_root = 'ROOT="${EDGE1_RELEASE_ROOT:-/opt/edge1-management-interface}"'
    old_dest = "DEST=/var/www/edge1-status"
    old_backup = 'BACKUP="/var/backups/edge1-unified-publish-$STAMP"'
    root_guard = ('test "$(id -u)" -eq 0 || {\n'
                  '    echo "STOP: --apply requires root" >&2\n'
                  '    exit 1\n'
                  '}')
    for part in (old_root, old_backup, root_guard):
        require(original.count(part) == 1, "Publisher fixture guard changed: " + part)
    require(original.count(old_dest) == 2, "Expected main and rollback destinations")

    with tempfile.TemporaryDirectory(prefix="edge1-publisher-fixture-") as temp:
        base = Path(temp)
        fake_root = base / "repository"
        fake_dest = base / "published"
        backups = base / "backups"
        fake_root.mkdir()
        fake_dest.mkdir()
        backups.mkdir()
        for source in EXPECTED:
            target = fake_root / source
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / source, target)

        # An isolated publisher COPY is required; never modify the real script.
        fixture = original.replace(old_root, 'ROOT="' + str(fake_root) + '"')
        fixture = fixture.replace(old_dest, 'DEST="' + str(fake_dest) + '"')
        fixture = fixture.replace(old_backup,
                                  'BACKUP="' + str(backups) +
                                  '/edge1-unified-publish-$STAMP"')
        fixture = fixture.replace(root_guard, "true # fixture only: nonroot allowed")
        require("DEST=/var/www/edge1-status" not in fixture,
                "Fixture retained a production destination")
        script = base / "publisher-fixture.sh"
        script.write_text(fixture, encoding="utf-8")
        subprocess.run(["bash", "-n", str(script)], check=True)

        # Half the assets already existed; the rest must be removed by rollback.
        originals: dict[str, bytes | None] = {}
        for i, relative in enumerate(EXPECTED.values()):
            target = fake_dest / relative
            if i % 2 == 0:
                target.parent.mkdir(parents=True, exist_ok=True)
                payload = ("previous-" + relative).encode()
                target.write_bytes(payload)
                originals[relative] = payload
            else:
                originals[relative] = None
        sentinel = fake_dest / "do-not-touch.txt"
        sentinel.write_text("untouched")

        # A missing required source must fail BEFORE altering the destination.
        first = next(iter(EXPECTED))
        hidden = fake_root / first
        missing = hidden.with_suffix(".temporarily-missing")
        hidden.rename(missing)
        failed = subprocess.run(["bash", str(script), "--apply"],
                                text=True, capture_output=True)
        require(failed.returncode != 0, "Missing-source preflight did not fail")
        require(sentinel.read_text() == "untouched", "Preflight touched destination")
        missing.rename(hidden)

        dry = subprocess.run(["bash", str(script)], text=True, capture_output=True)
        require(dry.returncode == 0 and not list(backups.iterdir()),
                "Dry run failed or wrote backup")
        deployed = subprocess.run(["bash", str(script), "--apply"],
                                  text=True, capture_output=True)
        require(deployed.returncode == 0,
                "Fixture publish failed: " + deployed.stdout + deployed.stderr)

        folders = list(backups.iterdir())
        require(len(folders) == 1, "Expected one fixture backup")
        backup = folders[0]
        manifest = (backup / "manifest").read_text().splitlines()
        require(len(manifest) == len(EXPECTED), "Backup manifest missing assets")
        for relative in EXPECTED.values():
            actual = (fake_dest / relative).read_bytes()
            source = next(k for k, v in EXPECTED.items() if v == relative)
            require(hashlib.sha256(actual).digest() ==
                    hashlib.sha256((fake_root / source).read_bytes()).digest(),
                    "Published asset differs: " + relative)
        require(sentinel.read_text() == "untouched", "Publisher changed unrelated file")

        rollback = subprocess.run(["bash", str(backup / "rollback.sh")],
                                  text=True, capture_output=True)
        require(rollback.returncode == 0,
                "Fixture rollback failed: " + rollback.stdout + rollback.stderr)
        for relative, previous in originals.items():
            target = fake_dest / relative
            if previous is None:
                require(not target.exists(), "Rollback retained new asset: " + relative)
            else:
                require(target.read_bytes() == previous,
                        "Rollback failed to restore: " + relative)
        require(sentinel.read_text() == "untouched", "Rollback changed unrelated file")
    print("PASS: Isolated publisher missing-source, dry-run, publish and rollback")


if __name__ == "__main__":
    validate_sources()
    test_publisher_fixture()
    print("PASS: Unified publisher fixture validation complete; production untouched")
