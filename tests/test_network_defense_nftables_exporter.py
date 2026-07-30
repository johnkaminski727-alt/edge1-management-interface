#!/usr/bin/env python3
import datetime as dt
import importlib.util
import json
import pathlib
import tempfile
import unittest

MODULE_PATH = pathlib.Path(__file__).parents[1] / 'server' / 'network_defense_nftables_exporter.py'
SPEC = importlib.util.spec_from_file_location('network_defense_nftables_exporter', MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def base_snapshot():
    return {
        'schema_version': '1.2',
        'read_only': True,
        'traffic_controls_changed': False,
        'privacy': {},
        'overall_state': 'limited',
        'sources': {
            'spamhaus_live_state': {'available': True, 'stale': False},
            'fail2ban_live_state': {'available': True, 'stale': False},
        },
        'components': {
            'spamhaus': {'observed': True, 'enforcement_verified': True},
            'fail2ban': {'observed': True, 'enforcement_verified': False},
            'firewall': {
                'name': 'Firewall visibility',
                'state': 'not_observed',
                'observed': False,
                'enforcement_verified': False,
                'detail': 'No normalized firewall-event telemetry is available.',
                'metrics': {'recent_events': 0},
            },
        },
        'summary': {},
        'warnings': [],
        'recommendations': [
            'Publish normalized nftables counters and service posture without exposing the full ruleset.'
        ],
        'limitations': [
            'DNS, general firewall, Fail2ban packet enforcement, and proxy enforcement remain unverified unless dedicated verification exists.'
        ],
    }


def nftables_document(state='ruleset_observed'):
    return {
        'contract': MODULE.CONTRACT,
        'read_only': True,
        'traffic_controls_changed': False,
        'privacy': {
            'addresses_included': False,
            'interfaces_included': False,
            'table_names_included': False,
            'chain_names_included': False,
            'set_names_included': False,
            'set_elements_included': False,
            'map_elements_included': False,
            'rule_expressions_included': False,
            'rule_comments_included': False,
            'rule_handles_included': False,
            'full_ruleset_included': False,
            'raw_command_output_included': False,
            'credentials_included': False,
            'private_keys_included': False,
        },
        'service': {
            'loaded': True,
            'active_state': 'active',
            'result': 'success',
        },
        'observation': {
            'state': state,
            'observed': state in {'ruleset_observed', 'partial', 'empty'},
            'enforcement_verified': False,
            'detail': 'Sanitized nftables aggregates were observed.',
        },
        'aggregates': {
            'objects': {
                'table': 5, 'chain': 17, 'rule': 83, 'set': 4, 'map': 2,
                'counter': 3, 'quota': 0, 'limit': 2, 'flowtable': 0,
                'ct helper': 0, 'ct timeout': 0, 'ct expectation': 0,
                'synproxy': 0, 'other': 0,
            },
            'families': {'ip': 1, 'ip6': 1, 'inet': 25, 'arp': 0, 'bridge': 0, 'netdev': 0, 'other': 0},
            'base_chains': {
                'count': 7,
                'hooks': {
                    'prerouting': 1, 'input': 2, 'forward': 1, 'output': 2,
                    'postrouting': 1, 'ingress': 0, 'egress': 0, 'other': 0,
                },
                'policies': {'accept': 5, 'drop': 2, 'other': 0},
            },
            'rules': {
                'with_counters': 40,
                'with_verdicts': 50,
                'verdicts': {
                    'accept': 20, 'drop': 12, 'reject': 3, 'continue': 0,
                    'return': 5, 'jump': 8, 'goto': 2, 'queue': 0,
                },
            },
            'elements': {'set_count': 1200, 'map_count': 3},
            'counter_totals': {'statement_count': 40, 'packets': 9000, 'bytes': 4500000},
        },
        'secret_table_name': 'must-not-leak',
        'secret_address': '203.0.113.99',
    }


class NetworkDefenseNftablesExporterTests(unittest.TestCase):
    def test_aggregate_ruleset_is_observed_without_enforcement_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / 'live-state.json'
            document = nftables_document()
            path.write_text(json.dumps(document), encoding='utf-8')
            now = dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc)
            snapshot = MODULE.augment_snapshot(base_snapshot(), document, None, path, now)
        component = snapshot['components']['firewall']
        self.assertEqual(component['state'], 'ruleset_observed')
        self.assertTrue(component['observed'])
        self.assertFalse(component['enforcement_verified'])
        self.assertEqual(component['metrics']['tables'], 5)
        self.assertEqual(component['metrics']['chains'], 17)
        self.assertEqual(component['metrics']['rules'], 83)
        self.assertEqual(component['metrics']['counter_packets'], 9000)
        self.assertEqual(component['metrics']['policies']['drop'], 2)
        self.assertEqual(snapshot['summary']['verified_enforcement_count'], 1)
        self.assertEqual(snapshot['schema_version'], '1.3')

    def test_invalid_privacy_or_enforcement_contract_is_rejected(self):
        privacy = nftables_document()
        privacy['privacy']['table_names_included'] = True
        self.assertEqual(
            MODULE.validate_nftables(privacy, None),
            'nftables aggregate live-state privacy contract is invalid',
        )
        enforcement = nftables_document()
        enforcement['observation']['enforcement_verified'] = True
        self.assertEqual(
            MODULE.validate_nftables(enforcement, None),
            'general nftables aggregate status must not claim enforcement verification',
        )

    def test_stale_source_withdraws_current_topology_assertion(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / 'live-state.json'
            document = nftables_document()
            path.write_text(json.dumps(document), encoding='utf-8')
            modified = dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc)
            now = modified + dt.timedelta(seconds=MODULE.NFTABLES_STALE_SECONDS + 1)
            snapshot = MODULE.augment_snapshot(base_snapshot(), document, None, path, now)
        self.assertEqual(snapshot['components']['firewall']['state'], 'stale')
        self.assertFalse(snapshot['components']['firewall']['enforcement_verified'])
        self.assertIn('nftables aggregate live-state snapshot is stale', snapshot['warnings'])
        self.assertEqual(snapshot['summary']['verified_enforcement_count'], 1)

    def test_public_snapshot_exposes_counts_not_private_ruleset_data(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / 'live-state.json'
            document = nftables_document()
            path.write_text(json.dumps(document), encoding='utf-8')
            now = dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc)
            snapshot = MODULE.augment_snapshot(base_snapshot(), document, None, path, now)
        rendered = json.dumps(snapshot)
        self.assertNotIn('must-not-leak', rendered)
        self.assertNotIn('203.0.113.99', rendered)
        self.assertNotIn('secret_table_name', rendered)
        self.assertFalse(snapshot['privacy']['firewall_addresses_included'])
        self.assertFalse(snapshot['privacy']['firewall_names_included'])
        self.assertFalse(snapshot['privacy']['firewall_rule_expressions_included'])

    def test_missing_source_keeps_existing_event_visibility(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / 'missing.json'
            snapshot = MODULE.augment_snapshot(
                base_snapshot(), {}, 'nftables aggregate live-state source is missing', path,
                dt.datetime(2026, 7, 30, 1, 30, tzinfo=dt.timezone.utc),
            )
        self.assertEqual(snapshot['components']['firewall']['state'], 'not_observed')
        self.assertIn('nftables aggregate live-state source is missing', snapshot['warnings'])
        self.assertEqual(snapshot['summary']['verified_enforcement_count'], 1)


if __name__ == '__main__':
    unittest.main()
