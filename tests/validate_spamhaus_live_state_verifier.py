#!/usr/bin/env python3
import datetime as dt
import importlib.util
import json
import pathlib
import subprocess
import tempfile
import unittest

MODULE_PATH = pathlib.Path(__file__).parents[1] / 'server' / 'spamhaus_live_state_verifier.py'
SPEC = importlib.util.spec_from_file_location('spamhaus_live_state_verifier', MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def sample_nft_document():
    return {
        'nftables': [
            {'table': {'family': 'inet', 'name': 'bigbird_spamhaus'}},
            {'set': {
                'family': 'inet', 'table': 'bigbird_spamhaus', 'name': 'drop4',
                'flags': ['interval'],
                'elem': [
                    {'prefix': {'addr': '192.0.2.0', 'len': 24}},
                    {'prefix': {'addr': '198.51.100.0', 'len': 24}},
                ],
            }},
            {'set': {
                'family': 'inet', 'table': 'bigbird_spamhaus', 'name': 'drop6',
                'flags': ['interval'],
                'elem': [{'prefix': {'addr': '2001:db8::', 'len': 32}}],
            }},
            {'chain': {
                'family': 'inet', 'table': 'bigbird_spamhaus', 'name': 'input',
                'hook': 'input', 'policy': 'accept', 'prio': -110,
            }},
            {'chain': {
                'family': 'inet', 'table': 'bigbird_spamhaus', 'name': 'forward',
                'hook': 'forward', 'policy': 'accept', 'prio': -110,
            }},
            {'rule': {
                'family': 'inet', 'table': 'bigbird_spamhaus', 'chain': 'input',
                'expr': [{'match': {'right': '@drop4'}}, {'counter': {}}, {'drop': None}],
            }},
            {'rule': {
                'family': 'inet', 'table': 'bigbird_spamhaus', 'chain': 'forward',
                'expr': [{'match': {'right': '@drop4'}}, {'counter': {}}, {'drop': None}],
            }},
            {'rule': {
                'family': 'inet', 'table': 'bigbird_spamhaus', 'chain': 'input',
                'expr': [{'match': {'right': '@drop6'}}, {'counter': {}}, {'drop': None}],
            }},
            {'rule': {
                'family': 'inet', 'table': 'bigbird_spamhaus', 'chain': 'forward',
                'expr': [{'match': {'right': '@drop6'}}, {'counter': {}}, {'drop': None}],
            }},
        ]
    }


class SpamhausLiveStateVerifierTests(unittest.TestCase):
    def test_complete_filter_is_verified(self):
        snapshot = MODULE.build_snapshot(
            nft_document=sample_nft_document(),
            nft_error=None,
            service={
                'Result': 'success',
                'ExecMainStatus': '0',
                'ActiveState': 'inactive',
                'SubState': 'dead',
            },
            timer_active='active',
            timer_enabled='enabled',
            now=dt.datetime(2026, 7, 29, 17, 0, tzinfo=dt.timezone.utc),
        )
        self.assertTrue(snapshot['enforcement']['verified'])
        self.assertEqual(snapshot['enforcement']['state'], 'active_verified')
        self.assertEqual(snapshot['sets']['drop4']['element_count'], 2)
        self.assertEqual(snapshot['sets']['drop6']['element_count'], 1)
        self.assertEqual(snapshot['rules']['input_ipv4_drop'], 1)
        self.assertEqual(snapshot['rules']['forward_ipv6_drop'], 1)
        self.assertFalse(snapshot['traffic_controls_changed'])

    def test_missing_timer_is_partial_not_verified(self):
        snapshot = MODULE.build_snapshot(
            nft_document=sample_nft_document(),
            nft_error=None,
            service={'Result': 'success', 'ExecMainStatus': '0'},
            timer_active='inactive',
            timer_enabled='enabled',
        )
        self.assertFalse(snapshot['enforcement']['verified'])
        self.assertEqual(snapshot['enforcement']['state'], 'partial')
        self.assertIn('filter timer is not active and enabled', snapshot['errors'])

    def test_absent_table_is_reported_without_failure(self):
        snapshot = MODULE.build_snapshot(
            nft_document={'nftables': []},
            nft_error=None,
            service={'Result': 'success', 'ExecMainStatus': '0'},
            timer_active='active',
            timer_enabled='enabled',
        )
        self.assertFalse(snapshot['enforcement']['verified'])
        self.assertEqual(snapshot['enforcement']['state'], 'not_present')
        self.assertFalse(snapshot['table']['present'])

    def test_published_snapshot_excludes_addresses_and_raw_ruleset(self):
        snapshot = MODULE.build_snapshot(
            nft_document=sample_nft_document(),
            nft_error=None,
            service={'Result': 'success', 'ExecMainStatus': '0'},
            timer_active='active',
            timer_enabled='enabled',
        )
        rendered = json.dumps(snapshot)
        self.assertNotIn('192.0.2.0', rendered)
        self.assertNotIn('2001:db8', rendered)
        self.assertNotIn('nftables', snapshot)
        self.assertFalse(snapshot['privacy']['set_elements_included'])
        self.assertFalse(snapshot['privacy']['full_ruleset_included'])
        self.assertFalse(snapshot['privacy']['raw_command_output_included'])

    def test_live_collection_uses_only_read_commands(self):
        calls = []

        def runner(args):
            calls.append(list(args))
            if '-j' in args:
                return subprocess.CompletedProcess(args, 0, json.dumps(sample_nft_document()), '')
            if 'show' in args:
                return subprocess.CompletedProcess(
                    args, 0,
                    'Result=success\nExecMainStatus=0\nActiveState=inactive\nSubState=dead\n',
                    '',
                )
            if 'is-active' in args:
                return subprocess.CompletedProcess(args, 0, 'active\n', '')
            return subprocess.CompletedProcess(args, 0, 'enabled\n', '')

        snapshot = MODULE.collect_live_state(
            nft_path=pathlib.Path('/usr/sbin/nft'),
            systemctl_path=pathlib.Path('/usr/bin/systemctl'),
            runner=runner,
        )
        self.assertTrue(snapshot['enforcement']['verified'])
        self.assertEqual(calls[0], [
            '/usr/sbin/nft', '-j', 'list', 'table', 'inet', 'bigbird_spamhaus'
        ])
        rendered_calls = '\n'.join(' '.join(call) for call in calls)
        for forbidden in (' add ', ' delete ', ' flush ', ' insert ', ' replace ', ' -f '):
            self.assertNotIn(forbidden, f' {rendered_calls} ')

    def test_atomic_write(self):
        with tempfile.TemporaryDirectory() as directory:
            output = pathlib.Path(directory) / 'live-state.json'
            snapshot = MODULE.build_snapshot(
                nft_document=sample_nft_document(),
                nft_error=None,
                service={'Result': 'success', 'ExecMainStatus': '0'},
                timer_active='active',
                timer_enabled='enabled',
            )
            MODULE.write_snapshot(snapshot, output)
            written = json.loads(output.read_text(encoding='utf-8'))
            self.assertEqual(written['contract'], MODULE.SCHEMA_VERSION)
            self.assertTrue(written['read_only'])


if __name__ == '__main__':
    unittest.main()
