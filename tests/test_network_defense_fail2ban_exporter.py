#!/usr/bin/env python3
import datetime as dt
import importlib.util
import json
import pathlib
import tempfile
import unittest

MODULE_PATH = pathlib.Path(__file__).parents[1] / 'server' / 'network_defense_fail2ban_exporter.py'
SPEC = importlib.util.spec_from_file_location('network_defense_fail2ban_exporter', MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def base_snapshot():
    return {
        'schema_version': '1.1',
        'read_only': True,
        'traffic_controls_changed': False,
        'privacy': {},
        'overall_state': 'limited',
        'sources': {'spamhaus_live_state': {'available': True, 'stale': False}},
        'components': {
            'spamhaus': {'observed': True, 'enforcement_verified': True},
            'fail2ban': {
                'name': 'Fail2ban visibility',
                'state': 'not_observed',
                'observed': False,
                'enforcement_verified': False,
                'detail': 'No normalized Fail2ban telemetry is available.',
                'metrics': {'recent_events': 0},
            },
        },
        'summary': {},
        'warnings': [],
        'recommendations': [
            'Publish Fail2ban jail health and aggregate ban counts without client-identifying log content.'
        ],
        'limitations': [
            'DNS, general firewall, Fail2ban, and proxy enforcement remain unverified until dedicated sanitized status exporters exist.'
        ],
    }


def fail2ban_document(state='active_observed'):
    return {
        'contract': MODULE.CONTRACT,
        'read_only': True,
        'traffic_controls_changed': False,
        'privacy': {
            'banned_addresses_included': False,
            'log_paths_included': False,
            'raw_client_output_included': False,
            'commands_included': False,
            'credentials_included': False,
            'private_keys_included': False,
        },
        'service': {
            'installed': True,
            'active': True,
            'active_state': 'active',
        },
        'client': {'socket_reachable': True},
        'jails': {
            'declared_count': 2,
            'observed_count': 2,
            'aggregate': {
                'currently_failed': 1,
                'total_failed': 15,
                'currently_banned': 3,
                'total_banned': 11,
            },
        },
        'observation': {
            'state': state,
            'jail_health_observed': state in {'active_observed', 'partial', 'inactive'},
            'enforcement_verified': False,
            'detail': 'Sanitized Fail2ban health was observed.',
        },
    }


class NetworkDefenseFail2banExporterTests(unittest.TestCase):
    def test_active_health_is_observed_without_incrementing_enforcement(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / 'live-state.json'
            path.write_text(json.dumps(fail2ban_document()), encoding='utf-8')
            now = dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc)
            snapshot = MODULE.augment_snapshot(base_snapshot(), fail2ban_document(), None, path, now)
        component = snapshot['components']['fail2ban']
        self.assertEqual(component['state'], 'active_observed')
        self.assertTrue(component['observed'])
        self.assertFalse(component['enforcement_verified'])
        self.assertEqual(component['metrics']['currently_banned'], 3)
        self.assertEqual(snapshot['summary']['verified_enforcement_count'], 1)
        self.assertEqual(snapshot['schema_version'], '1.2')

    def test_invalid_privacy_contract_is_rejected(self):
        document = fail2ban_document()
        document['privacy']['banned_addresses_included'] = True
        self.assertEqual(
            MODULE.validate_fail2ban(document, None),
            'fail2ban live-state privacy contract is invalid',
        )

    def test_stale_source_withdraws_current_health_assertion(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / 'live-state.json'
            path.write_text(json.dumps(fail2ban_document()), encoding='utf-8')
            modified = dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc)
            now = modified + dt.timedelta(seconds=MODULE.FAIL2BAN_STALE_SECONDS + 1)
            snapshot = MODULE.augment_snapshot(base_snapshot(), fail2ban_document(), None, path, now)
        self.assertEqual(snapshot['components']['fail2ban']['state'], 'stale')
        self.assertFalse(snapshot['components']['fail2ban']['enforcement_verified'])
        self.assertIn('fail2ban live-state snapshot is stale', snapshot['warnings'])

    def test_public_snapshot_exposes_aggregates_not_jail_records(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / 'live-state.json'
            document = fail2ban_document()
            document['jails']['records'] = [{'name': 'sshd', 'currently_banned': 3}]
            path.write_text(json.dumps(document), encoding='utf-8')
            now = dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc)
            snapshot = MODULE.augment_snapshot(base_snapshot(), document, None, path, now)
        rendered = json.dumps(snapshot)
        self.assertNotIn('records', snapshot['components']['fail2ban']['metrics'])
        self.assertNotIn('sshd', rendered)
        self.assertFalse(snapshot['privacy']['fail2ban_banned_addresses_included'])


if __name__ == '__main__':
    unittest.main()
