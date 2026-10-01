#!/usr/bin/env python3
"""Validate read-only Network Defense source provenance and UI state.

Checks the source against the four accepted page contracts and uses Node,
when present, to syntax-check the embedded browser script. No network access
or production file writes.
"""
from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

PAGE = Path(__file__).resolve().parents[1] / "src/web/network-defense/index.html"


class Elements(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.scripts = []
        self.in_inline_script = False
        self.buffer = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if values.get("id"):
            self.ids.append(values["id"])
        if tag == "script" and not values.get("src"):
            self.in_inline_script = True
            self.buffer = []

    def handle_data(self, data):
        if self.in_inline_script:
            self.buffer.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self.in_inline_script:
            self.scripts.append("".join(self.buffer))
            self.in_inline_script = False


def main():
    html = PAGE.read_text(encoding="utf-8")
    parser = Elements()
    parser.feed(html)
    assert len(parser.ids) == len(set(parser.ids)), "Duplicate DOM IDs"
    for name in ("source-overview", "current-sources", "legacy-sources",
                 "connection-status", "freshness", "refresh-button"):
        assert name in parser.ids, "Missing source/freshness region: " + name
    assert len(parser.scripts) == 1, "Expected one inline application script"
    js = parser.scripts[0]
    for term in ('CURRENT_COLLECTORS=new Set(["core_live","crowdsec_live"])',
                 "sourcePresentation(name,x)", "snapshotAgeSeconds()",
                 "stale_after_seconds", "Not staged", "Not connected",
                 "Age unknown", "Summary snapshot", "Browser refreshed",
                 "not service-health counts"):
        assert term in js, "Missing presentation contract: " + term
    assert 'const ENDPOINT="/edge1-ops/status/network-defense/data/network-defense.json"' in js
    assert 'traffic_controls_changed:false' in html
    assert not re.search(r'fetch\s*\([^)]*,\s*\{[^}]*method\s*:\s*["\'](?:POST|PUT|PATCH|DELETE)', js, re.I|re.S)

    node = shutil.which("node")
    if node:
        with tempfile.TemporaryDirectory(prefix="network-freshness-") as folder:
            script = Path(folder) / "network-defense.js"
            script.write_text(js, encoding="utf-8")
            subprocess.run([node, "--check", str(script)], check=True)
        print("PASS: Embedded JavaScript syntax checked")
    else:
        print("SKIP: Node unavailable; browser script syntax not checked")
    print("PASS: Current/legacy source separation and read-only freshness contract")


if __name__ == "__main__":
    main()
