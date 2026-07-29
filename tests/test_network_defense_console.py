#!/usr/bin/env python3
"""Static safety checks for Network Defense console."""

import re
import unittest
from html.parser import HTMLParser
from pathlib import Path

PAGE = Path(__file__).parents[1] / 'src' / 'web' / 'network-defense' / 'index.html'


class IdCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key == 'id' and value:
                self.ids.append(value)


class NetworkDefenseConsoleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = PAGE.read_text(encoding='utf-8')

    def test_required_interface_regions_exist(self):
        for token in ('Network Defense', 'Defense posture', 'Defense layers', 'Source freshness', 'Safety boundary'):
            self.assertIn(token, self.source)

    def test_ids_are_unique(self):
        parser = IdCollector()
        parser.feed(self.source)
        self.assertEqual(len(parser.ids), len(set(parser.ids)))

    def test_only_approved_status_endpoint_is_used(self):
        endpoints = set(re.findall(r'/(?:edge1-status|api)/[^"\']+\.json', self.source))
        self.assertEqual(endpoints, {'/edge1-status/network-defense.json'})

    def test_no_write_capable_fetch(self):
        self.assertIsNone(re.search(r'''fetch\s*\([^)]*,\s*\{[^}]*method\s*:\s*["'](?:POST|PUT|PATCH|DELETE)["']''', self.source, re.I | re.S))

    def test_resilience_controls_exist(self):
        for token in ('AbortController', 'REQUEST_TIMEOUT_MS', 'REFRESH_INTERVAL_MS', 'visibilitychange', 'last successful snapshot'):
            self.assertIn(token, self.source)

    def test_read_only_boundary_is_visible(self):
        for token in ('read-only', 'does not install', 'traffic_controls_changed:false'):
            self.assertIn(token, self.source)


if __name__ == '__main__':
    unittest.main()
