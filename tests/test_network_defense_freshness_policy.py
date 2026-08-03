#!/usr/bin/env python3
"""Validation for schedule-aware Network Defense freshness limits."""

import datetime as dt
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / 'server' / 'network_defense_freshness_exporter.py'
SENSOR_PATH = Path(__file__).parents[1] / 'server' / 'network_defense_sensor_exporter.py'
SERVICE_PATH = Path(__file__).parents[1] / 'deploy' / 'systemd' / 'wwcx-network-defense.service'
SPEC = importlib.util.spec_from_file_location('network_defense_freshness_exporter', MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)
BASE = MODULE.FINAL.BASE.BASE.BASE


class NetworkDefenseFreshnessPolicyTests(unittest.TestCase):
    def source_at_age(self, age_seconds: int):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'operations-network.json'
            path.write_text('{}', encoding='utf-8')
            now = dt.datetime(2026, 7, 30, 12, 0, tzinfo=dt.timezone.utc)
            modified = now - dt.timedelta(seconds=age_seconds)
            os.utime(path, (modified.timestamp(), modified.timestamp()))
            return BASE.source_record(path, 'network', None, now)

    def test_network_threshold_matches_two_producer_intervals(self):
        self.assertEqual(MODULE.NETWORK_STALE_SECONDS, 600)
        self.assertEqual(BASE.SOURCE_STALE_SECONDS['network'], 600)

    def test_normal_between_run_age_remains_fresh(self):
        record = self.source_at_age(7 * 60)
        self.assertFalse(record['stale'])
        self.assertEqual(record['stale_after_seconds'], 600)

    def test_two_missed_intervals_are_stale(self):
        record = self.source_at_age(10 * 60 + 1)
        self.assertTrue(record['stale'])

    def test_other_source_thresholds_remain_unchanged(self):
        self.assertEqual(BASE.SOURCE_STALE_SECONDS['security'], 5 * 60)
        self.assertEqual(BASE.SOURCE_STALE_SECONDS['correlation'], 5 * 60)
        self.assertEqual(BASE.SOURCE_STALE_SECONDS['operations'], 5 * 60)
        self.assertEqual(BASE.SOURCE_STALE_SECONDS['spamhaus'], 8 * 60 * 60)
        self.assertEqual(BASE.SOURCE_STALE_SECONDS['spamhaus_live_state'], 5 * 60)

    def test_service_uses_sensor_wrapper_over_final_freshness_layer(self):
        service = SERVICE_PATH.read_text(encoding='utf-8')
        sensor = SENSOR_PATH.read_text(encoding='utf-8')
        self.assertIn('server/network_defense_sensor_exporter.py', service)
        self.assertIn('network_defense_freshness_exporter', sensor)
        self.assertIn('RestrictAddressFamilies=AF_UNIX', service)
        self.assertIn('CapabilityBoundingSet=\n', service)
        self.assertIn('AmbientCapabilities=\n', service)

    def test_wrappers_have_no_command_or_network_execution(self):
        for path in (MODULE_PATH, SENSOR_PATH):
            source = path.read_text(encoding='utf-8')
            for token in ('subprocess', 'socket', 'requests', 'urllib.request', 'os.system', 'Popen('):
                self.assertNotIn(token, source)


if __name__ == '__main__':
    unittest.main()
