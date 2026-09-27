#!/usr/bin/env python3
"""Offline regression checks for the Spamhaus DROP JSON parser and nft candidate."""
from __future__ import annotations

import datetime as dt
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "tools/networking/spamhaus_feed_candidate.py"
SPEC = importlib.util.spec_from_file_location("spamhaus_candidate", SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SpamhausCandidateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.now = dt.datetime.now(dt.timezone.utc)
        self.timestamp = int(self.now.timestamp())

    def feed(self, name, rows):
        path = self.folder / name
        path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        return path

    def test_valid_jsonl_deduplicates_and_renders_both_hooks(self):
        v4 = self.feed("ipv4.json", [
            {"cidr": "8.8.8.0/25"}, {"cidr": "8.8.8.128/25"},
            {"cidr": "8.8.8.0/25"}, {"timestamp": self.timestamp},
        ])
        v6 = self.feed("ipv6.json", [
            {"cidr": "2001:4860::/32"}, {"timestamp": self.timestamp},
        ])
        addresses4, count4 = MODULE.parse_feed(v4, 4, self.now)
        addresses6, count6 = MODULE.parse_feed(v6, 6, self.now)
        self.assertEqual((count4, count6), (2, 1))
        self.assertEqual([str(item) for item in addresses4], ["8.8.8.0/24"])
        candidate = MODULE.render_candidate(addresses4, addresses6)
        self.assertIn("priority -110", candidate)
        self.assertIn("hook input", candidate)
        self.assertIn("hook forward", candidate)
        self.assertIn("ip6 saddr @drop6 counter drop", candidate)
        self.assertNotIn("delete table", candidate)
        self.assertIn("delete table inet bigbird_spamhaus",
                      MODULE.render_candidate(addresses4, addresses6, replace=True))

    def test_empty_feed_rejected(self):
        path = self.feed("empty.json", [{"timestamp": self.timestamp}])
        with self.assertRaises(ValueError):
            MODULE.parse_feed(path, 4, self.now)

    def test_non_global_or_family_mismatch_rejected(self):
        for cidr in ("10.0.0.0/8", "2001:4860::/32"):
            with self.subTest(cidr=cidr):
                path = self.feed("bad.json", [
                    {"cidr": cidr}, {"timestamp": self.timestamp},
                ])
                with self.assertRaises(ValueError):
                    MODULE.parse_feed(path, 4, self.now)

    def test_stale_and_future_metadata_rejected(self):
        for seconds in (-73 * 3600, 16 * 60):
            with self.subTest(seconds=seconds):
                path = self.feed("bad.json", [
                    {"cidr": "8.8.8.0/24"},
                    {"timestamp": self.timestamp + seconds},
                ])
                with self.assertRaises(ValueError):
                    MODULE.parse_feed(path, 4, self.now)

    def test_missing_and_duplicate_metadata_rejected(self):
        for metadata in ([], [
            {"timestamp": self.timestamp}, {"timestamp": self.timestamp}
        ]):
            with self.subTest(metadata=metadata):
                path = self.feed("bad.json", [{"cidr": "8.8.8.0/24"}, *metadata])
                with self.assertRaises(ValueError):
                    MODULE.parse_feed(path, 4, self.now)

    def test_unrecognized_record_and_bad_cidr_rejected(self):
        for bad in ({"foo": 1}, {"cidr": "not-an-address"}):
            with self.subTest(bad=bad):
                path = self.feed("bad.json", [bad, {"timestamp": self.timestamp}])
                with self.assertRaises((ValueError, TypeError)):
                    MODULE.parse_feed(path, 4, self.now)

    def test_requires_both_families(self):
        with self.assertRaises(ValueError):
            MODULE.render_candidate([], ["placeholder"])


if __name__ == "__main__":
    unittest.main()
