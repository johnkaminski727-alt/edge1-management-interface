#!/usr/bin/env python3
"""Validation for staged DNS policy integration in Network Defense."""

import datetime as dt
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / 'server' / 'network_defense_dns_exporter.py'
SPEC = importlib.util.spec_from_file_location('network_defense_dns_exporter', MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class NetworkDefenseDnsExporterTests(unittest.TestCase):
    def base_snapshot(self):
        return {
            'summary': {},
            'sources': {},
            'components': {},
            'warnings': [],
            'recommendations': [],
            'limitations': [],
            'traffic_controls_changed': False,
        }

    def test_missing_policy_is_visible_without_claiming_enforcement(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'missing.json'
            result = MODULE.augment_snapshot(
                self.base_snapshot(), {}, 'dns policy status is not staged', path,
                dt.datetime(2026, 7, 29, 12, 0, tzinfo=dt.timezone.utc),
            )
            self.assertEqual(result['components']['dns_policy']['state'], 'not_staged')
            self.assertFalse(result['dns_policy']['policy_staged'])
            self.assertFalse(result['dns_policy']['enforcement_enabled'])
            self.assertFalse(result['dns_policy']['traffic_controls_changed'])

    def test_disabled_policy_is_reported_as_safely_staged(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'dns-defense-policy-status.json'
            document = {
                'activation_mode': 'staged_disabled',
                'enforcement_enabled': False,
                'traffic_controls_changed': False,
                'rpz_action_override': 'disabled',
                'policy': {
                    'name': 'wwcx-dns-defense.rpz',
                    'serial': 2026072901,
                    'entry_count': 3,
                    'expanded_record_count': 5,
                    'action_counts': {'nxdomain': 1, 'nodata': 1, 'passthru': 1},
                },
            }
            path.write_text(json.dumps(document), encoding='utf-8')
            result = MODULE.augment_snapshot(
                self.base_snapshot(), document, None, path,
                dt.datetime.now(dt.timezone.utc),
            )
            component = result['components']['dns_policy']
            self.assertEqual(component['state'], 'staged_disabled')
            self.assertTrue(result['dns_policy']['policy_staged'])
            self.assertFalse(component['enforcement_verified'])
            self.assertEqual(component['metrics']['entry_count'], 3)
            self.assertEqual(result['summary']['verified_enforcement_count'], 0)

    def test_unsafe_status_is_unverified(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'dns-defense-policy-status.json'
            document = {
                'activation_mode': 'active',
                'enforcement_enabled': True,
                'traffic_controls_changed': True,
                'rpz_action_override': 'nxdomain',
                'policy': {'name': 'wwcx-dns-defense.rpz', 'entry_count': 1},
            }
            path.write_text(json.dumps(document), encoding='utf-8')
            result = MODULE.augment_snapshot(
                self.base_snapshot(), document, None, path,
                dt.datetime.now(dt.timezone.utc),
            )
            self.assertEqual(result['components']['dns_policy']['state'], 'unverified')
            self.assertFalse(result['dns_policy']['policy_staged'])
            self.assertFalse(result['dns_policy']['enforcement_enabled'])
            self.assertFalse(result['dns_policy']['traffic_controls_changed'])
            self.assertTrue(result['warnings'])

    def test_exporter_has_no_command_or_network_execution(self):
        source = MODULE_PATH.read_text(encoding='utf-8')
        for token in ('subprocess', 'socket', 'requests', 'urllib.request', 'os.system', 'Popen('):
            self.assertNotIn(token, source)


if __name__ == '__main__':
    unittest.main()
