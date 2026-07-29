#!/usr/bin/env python3
"""Static validation for the read-only Security Operations console."""

from html.parser import HTMLParser
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
CONSOLE = ROOT / "src" / "web" / "security" / "index.html"


class ConsoleParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.scripts = []
        self._in_script = False
        self._script_parts = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if "id" in values:
            self.ids.append(values["id"])
        if tag == "script":
            self._in_script = True
            self._script_parts = []

    def handle_data(self, data):
        if self._in_script:
            self._script_parts.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self._in_script:
            self.scripts.append("".join(self._script_parts))
            self._in_script = False


class SecurityConsoleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = CONSOLE.read_text(encoding="utf-8")
        cls.parser = ConsoleParser()
        cls.parser.feed(cls.text)
        cls.script = "\n".join(cls.parser.scripts)

    def test_required_operator_views_exist(self):
        required = {
            "connection-status", "freshness", "overview", "threat-summary",
            "top-signatures", "top-sources", "health", "alerts",
            "validation", "advisories", "alert-search", "risk-filter",
            "alert-sort", "refresh-button", "download-button",
        }
        self.assertTrue(required.issubset(set(self.parser.ids)))

    def test_ids_are_unique(self):
        self.assertEqual(len(self.parser.ids), len(set(self.parser.ids)))

    def test_read_only_boundary_is_explicit(self):
        self.assertIn("This console does not issue live IDS, firewall, DNS, or proxy changes.", self.text)
        self.assertIn("No write path in this console", self.text)
        self.assertNotRegex(self.script, r"fetch\([^)]*,\s*\{[^}]*method\s*:\s*['\"](?:POST|PUT|PATCH|DELETE)")

    def test_resilience_controls_exist(self):
        for token in (
            "REQUEST_TIMEOUT_MS", "STALE_AFTER_MS", "AbortController",
            "showing last successful snapshot", "visibilitychange",
        ):
            self.assertIn(token, self.script)

    def test_alert_intelligence_controls_exist(self):
        for token in (
            "normalizeRisk", "filteredAlerts", "renderThreatSummary",
            "Top signatures", "Top sources", "Highest risk first",
        ):
            self.assertIn(token, self.text)

    def test_only_read_endpoint_is_configured(self):
        endpoint_matches = re.findall(r'const ENDPOINT\s*=\s*"([^"]+)"', self.script)
        self.assertEqual(endpoint_matches, ["/edge1-status/security-operations.json"])


if __name__ == "__main__":
    unittest.main()
