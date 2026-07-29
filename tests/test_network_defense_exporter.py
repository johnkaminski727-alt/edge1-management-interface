#!/usr/bin/env python3
"""Validation for network-defense observability export."""

import datetime as dt
import importlib.util
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / 'server' / 'network_defense_exporter.py'
SPEC = importlib.util.spec_from_file_location('network_defense_exporter', MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class NetworkDefenseExporterTests(unittest.TestCase):
    def write_json(self, root: Path, name: str, value):
        path = root / name
        path.write_text(json.dumps(value), encoding='utf-8')
        return path

    def touch_at(self, path: Path, when: dt.datetime):
        timestamp = when.timestamp()
        os.utime(path, (timestamp, timestamp))

    def test_missing_sources_degrade_without_claiming_enforcement(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = MODULE.build_snapshot(
                root / 'network.json', root / 'security.json',
                root / 'correlation.json', root / 'operations.json',
                root / 'spamhaus.txt')
            self.assertEqual(result['overall_state'], 'limited')
            self.assertTrue(result['warnings'])
            self.assertTrue(result['read_only'])
            self.assertFalse(result['traffic_controls_changed'])
            self.assertEqual(result['summary']['verified_enforcement_count'], 0)

    def test_observed_layers_are_reported_without_overclaiming(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            now = dt.datetime(2026, 7, 29, 12, 0, tzinfo=dt.timezone.utc)
            network = self.write_json(root, 'network.json', {'resolver': 'DNS Servers: 127.0.0.1'})
            security = self.write_json(root, 'security.json', {
                'health': {'status': 'healthy'},
                'engine': {'version': '8.0'},
                'recent_alerts': [{'signature': 'example'}],
            })
            correlation = self.write_json(root, 'correlation.json', {
                'summary': {'event_count': 9, 'correlation_count': 2,
                            'high_confidence_count': 1,
                            'category_counts': {'ids': 1, 'dns': 3, 'firewall': 4, 'fail2ban': 1}}
            })
            operations = self.write_json(root, 'operations.json', {})
            spamhaus = root / 'spamhaus.txt'
            spamhaus.write_text('drop4=10\nedrop4=2\ncombined4=11\ndrop6=3\n', encoding='utf-8')
            for path in (network, security, correlation, operations, spamhaus):
                self.touch_at(path, now)

            result = MODULE.build_snapshot(network, security, correlation, operations, spamhaus, now=now)
            self.assertEqual(result['overall_state'], 'observed')
            self.assertEqual(result['components']['ids']['state'], 'healthy')
            self.assertTrue(result['components']['dns']['observed'])
            self.assertEqual(result['components']['firewall']['metrics']['recent_events'], 4)
            self.assertEqual(result['components']['fail2ban']['metrics']['recent_events'], 1)
            self.assertEqual(result['components']['spamhaus']['metrics']['combined_ipv4_networks'], 11)
            self.assertFalse(result['components']['spamhaus']['enforcement_verified'])
            self.assertEqual(result['components']['proxy']['state'], 'not_configured')

    def test_stale_source_is_visible(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            now = dt.datetime(2026, 7, 29, 12, 0, tzinfo=dt.timezone.utc)
            old = now - dt.timedelta(hours=1)
            paths = [self.write_json(root, f'{name}.json', {}) for name in ('network', 'security', 'correlation', 'operations')]
            spamhaus = root / 'spamhaus.txt'
            spamhaus.write_text('combined4=1\n', encoding='utf-8')
            for path in paths:
                self.touch_at(path, old)
            self.touch_at(spamhaus, now)
            result = MODULE.build_snapshot(*paths, spamhaus, now=now)
            self.assertEqual(result['overall_state'], 'stale')
            self.assertIn('network', result['summary']['stale_sources'])

    def test_atomic_write_is_world_readable_not_executable(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'network-defense.json'
            MODULE.write_snapshot({'ok': True}, output)
            self.assertEqual(json.loads(output.read_text(encoding='utf-8'))['ok'], True)
            self.assertFalse(output.with_suffix('.json.tmp').exists())
            self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o644)

    def test_exporter_has_no_command_or_network_execution(self):
        source = MODULE_PATH.read_text(encoding='utf-8')
        for token in ('subprocess', 'socket', 'requests', 'urllib.request', 'os.system', 'Popen('):
            self.assertNotIn(token, source)


if __name__ == '__main__':
    unittest.main()
