#!/usr/bin/env python3
import datetime as dt
import importlib.util
import json
import pathlib
import subprocess
import tempfile
import unittest

MODULE_PATH = pathlib.Path(__file__).parents[1] / 'server' / 'fail2ban_live_state_verifier.py'
SPEC = importlib.util.spec_from_file_location('fail2ban_live_state_verifier', MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)

ROOT_STATUS = '''Status
|- Number of jail:\t2
`- Jail list:\tsshd, recidive
'''

SSHD_STATUS = '''Status for the jail: sshd
|- Filter
|  |- Currently failed:\t1
|  `- Total failed:\t12
`- Actions
   |- Currently banned:\t2
   |- Total banned:\t7
   `- Banned IP list:\t192.0.2.10 198.51.100.20
'''

RECIDIVE_STATUS = '''Status for the jail: recidive
|- Filter
|  |- Currently failed:\t0
|  `- Total failed:\t3
`- Actions
   |- Currently banned:\t1
   |- Total banned:\t4
   `- Banned IP list:\t203.0.113.30
'''

SERVICE = {
    'LoadState': 'loaded',
    'ActiveState': 'active',
    'SubState': 'running',
    'Result': 'success',
    'ExecMainStatus': '0',
    'UnitFileState': 'enabled',
}


class Fail2banLiveStateVerifierTests(unittest.TestCase):
    def test_complete_jail_health_is_observed_without_enforcement_claim(self):
        snapshot = MODULE.build_snapshot(
            service=SERVICE,
            client_returncode=0,
            declared_jail_count=2,
            jail_names=['sshd', 'recidive'],
            jail_records={
                'sshd': MODULE.parse_jail_status(SSHD_STATUS),
                'recidive': MODULE.parse_jail_status(RECIDIVE_STATUS),
            },
            now=dt.datetime(2026, 7, 29, 18, 45, tzinfo=dt.timezone.utc),
        )
        self.assertEqual(snapshot['observation']['state'], 'active_observed')
        self.assertTrue(snapshot['observation']['jail_health_observed'])
        self.assertFalse(snapshot['observation']['enforcement_verified'])
        self.assertEqual(snapshot['jails']['observed_count'], 2)
        self.assertEqual(snapshot['jails']['aggregate']['currently_banned'], 3)
        self.assertEqual(snapshot['jails']['aggregate']['total_banned'], 11)
        self.assertFalse(snapshot['traffic_controls_changed'])

    def test_status_parsing_sanitizes_jail_names(self):
        declared, names = MODULE.parse_status(
            'Number of jail: 4\nJail list: sshd, recidive, bad name, ../../unsafe\n'
        )
        self.assertEqual(declared, 4)
        self.assertEqual(names, ['sshd', 'recidive'])

    def test_inactive_service_is_reported_truthfully(self):
        service = dict(SERVICE, ActiveState='inactive', SubState='dead')
        snapshot = MODULE.build_snapshot(service, 1, 0, [], {})
        self.assertEqual(snapshot['observation']['state'], 'inactive')
        self.assertTrue(snapshot['observation']['jail_health_observed'])
        self.assertFalse(snapshot['observation']['enforcement_verified'])

    def test_missing_client_is_not_installed(self):
        snapshot = MODULE.build_snapshot(
            {'LoadState': 'not-found', 'ActiveState': 'inactive'}, 127, 0, [], {}
        )
        self.assertEqual(snapshot['observation']['state'], 'not_installed')
        self.assertFalse(snapshot['observation']['jail_health_observed'])

    def test_published_snapshot_excludes_addresses_paths_and_raw_output(self):
        snapshot = MODULE.build_snapshot(
            service=SERVICE,
            client_returncode=0,
            declared_jail_count=1,
            jail_names=['sshd'],
            jail_records={'sshd': MODULE.parse_jail_status(SSHD_STATUS)},
        )
        rendered = json.dumps(snapshot)
        for forbidden in ('192.0.2.10', '198.51.100.20', '/var/log/auth.log', 'Banned IP list'):
            self.assertNotIn(forbidden, rendered)
        self.assertFalse(snapshot['privacy']['banned_addresses_included'])
        self.assertFalse(snapshot['privacy']['raw_client_output_included'])
        self.assertFalse(snapshot['privacy']['commands_included'])

    def test_collection_uses_only_status_and_systemctl_show(self):
        calls = []

        def runner(args):
            calls.append(list(args))
            if args[1] == 'show':
                return subprocess.CompletedProcess(args, 0, ''.join(f'{k}={v}\n' for k, v in SERVICE.items()), '')
            if args[-1] == 'status':
                return subprocess.CompletedProcess(args, 0, ROOT_STATUS, '')
            if args[-1] == 'sshd':
                return subprocess.CompletedProcess(args, 0, SSHD_STATUS, '')
            return subprocess.CompletedProcess(args, 0, RECIDIVE_STATUS, '')

        snapshot = MODULE.collect_live_state(
            client_path=pathlib.Path('/usr/bin/fail2ban-client'),
            systemctl_path=pathlib.Path('/usr/bin/systemctl'),
            runner=runner,
        )
        self.assertEqual(snapshot['observation']['state'], 'active_observed')
        rendered_calls = '\n'.join(' '.join(call) for call in calls)
        self.assertIn('/usr/bin/fail2ban-client status', rendered_calls)
        for forbidden in (' set ', ' start ', ' stop ', ' reload ', ' restart ', ' unbanip ', ' banip '):
            self.assertNotIn(forbidden, f' {rendered_calls} ')

    def test_atomic_write(self):
        with tempfile.TemporaryDirectory() as directory:
            output = pathlib.Path(directory) / 'live-state.json'
            snapshot = MODULE.build_snapshot(SERVICE, 0, 0, [], {})
            MODULE.write_snapshot(snapshot, output)
            written = json.loads(output.read_text(encoding='utf-8'))
            self.assertEqual(written['contract'], MODULE.SCHEMA_VERSION)
            self.assertTrue(written['read_only'])


if __name__ == '__main__':
    unittest.main()
