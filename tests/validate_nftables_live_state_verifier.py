#!/usr/bin/env python3
import datetime as dt
import importlib.util
import json
import pathlib
import stat
import subprocess
import tempfile
import unittest

MODULE_PATH = pathlib.Path(__file__).parents[1] / 'server' / 'nftables_live_state_verifier.py'
SPEC = importlib.util.spec_from_file_location('nftables_live_state_verifier', MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def sample_ruleset():
    return {
        'nftables': [
            {'metainfo': {'json_schema_version': 1}},
            {'table': {'family': 'inet', 'name': 'private-filter', 'handle': 1}},
            {'table': {'family': 'ip', 'name': 'secret-nat', 'handle': 2}},
            {'chain': {
                'family': 'inet', 'table': 'private-filter', 'name': 'input-secret',
                'type': 'filter', 'hook': 'input', 'prio': 0, 'policy': 'drop', 'handle': 3,
            }},
            {'chain': {
                'family': 'inet', 'table': 'private-filter', 'name': 'output-secret',
                'type': 'filter', 'hook': 'output', 'prio': 0, 'policy': 'accept', 'handle': 4,
            }},
            {'chain': {
                'family': 'inet', 'table': 'private-filter', 'name': 'internal-chain', 'handle': 5,
            }},
            {'set': {
                'family': 'inet', 'table': 'private-filter', 'name': 'blocked-clients',
                'type': 'ipv4_addr', 'elem': ['192.0.2.10', '198.51.100.20'], 'handle': 6,
            }},
            {'map': {
                'family': 'inet', 'table': 'private-filter', 'name': 'private-map',
                'type': 'ipv4_addr : verdict', 'elem': [{'192.0.2.30': {'jump': 'internal-chain'}}],
            }},
            {'counter': {
                'family': 'inet', 'table': 'private-filter', 'name': 'named-secret-counter',
                'packets': 7, 'bytes': 700,
            }},
            {'rule': {
                'family': 'inet', 'table': 'private-filter', 'chain': 'input-secret', 'handle': 10,
                'comment': 'customer 203.0.113.8 on eth0',
                'expr': [
                    {'match': {'left': {'payload': {'protocol': 'ip', 'field': 'saddr'}}, 'op': '==', 'right': '203.0.113.8'}},
                    {'counter': {'packets': 11, 'bytes': 1100}},
                    {'drop': None},
                ],
            }},
            {'rule': {
                'family': 'inet', 'table': 'private-filter', 'chain': 'output-secret', 'handle': 11,
                'expr': [{'counter': {'packets': 13, 'bytes': 1300}}, {'accept': None}],
            }},
            {'rule': {
                'family': 'inet', 'table': 'private-filter', 'chain': 'input-secret', 'handle': 12,
                'expr': [{'reject': {'type': 'icmpx', 'expr': 'admin-prohibited'}}],
            }},
            {'rule': {
                'family': 'inet', 'table': 'private-filter', 'chain': 'input-secret', 'handle': 13,
                'expr': [{'jump': {'target': 'internal-chain'}}],
            }},
        ]
    }


class NftablesLiveStateVerifierTests(unittest.TestCase):
    def test_ruleset_is_reduced_to_sanitized_aggregates(self):
        snapshot = MODULE.build_snapshot(
            ruleset_document=sample_ruleset(),
            ruleset_error=None,
            service={
                'LoadState': 'loaded', 'ActiveState': 'active', 'SubState': 'exited',
                'UnitFileState': 'enabled', 'Result': 'success', 'ExecMainStatus': '0',
            },
            now=dt.datetime(2026, 7, 30, 1, 0, tzinfo=dt.timezone.utc),
        )
        self.assertEqual(snapshot['observation']['state'], 'ruleset_observed')
        self.assertTrue(snapshot['observation']['observed'])
        self.assertFalse(snapshot['observation']['enforcement_verified'])
        aggregates = snapshot['aggregates']
        self.assertEqual(aggregates['objects']['table'], 2)
        self.assertEqual(aggregates['objects']['chain'], 3)
        self.assertEqual(aggregates['objects']['rule'], 4)
        self.assertEqual(aggregates['objects']['set'], 1)
        self.assertEqual(aggregates['objects']['map'], 1)
        self.assertEqual(aggregates['base_chains']['count'], 2)
        self.assertEqual(aggregates['base_chains']['hooks']['input'], 1)
        self.assertEqual(aggregates['base_chains']['policies']['drop'], 1)
        self.assertEqual(aggregates['rules']['verdicts']['drop'], 1)
        self.assertEqual(aggregates['rules']['verdicts']['accept'], 1)
        self.assertEqual(aggregates['rules']['verdicts']['reject'], 1)
        self.assertEqual(aggregates['rules']['verdicts']['jump'], 1)
        self.assertEqual(aggregates['elements']['set_count'], 2)
        self.assertEqual(aggregates['elements']['map_count'], 1)
        self.assertEqual(aggregates['counter_totals']['statement_count'], 2)
        self.assertEqual(aggregates['counter_totals']['packets'], 24)
        self.assertEqual(aggregates['counter_totals']['bytes'], 2400)
        self.assertFalse(snapshot['traffic_controls_changed'])

    def test_snapshot_excludes_names_addresses_interfaces_and_rule_details(self):
        snapshot = MODULE.build_snapshot(
            ruleset_document=sample_ruleset(),
            ruleset_error=None,
            service={'LoadState': 'loaded', 'Result': 'success', 'ExecMainStatus': '0'},
        )
        rendered = json.dumps(snapshot)
        for forbidden in (
            'private-filter', 'secret-nat', 'input-secret', 'output-secret', 'internal-chain',
            'blocked-clients', 'private-map', 'named-secret-counter',
            '192.0.2.10', '198.51.100.20', '192.0.2.30', '203.0.113.8',
            'eth0', 'customer', 'payload', 'saddr', 'admin-prohibited',
        ):
            self.assertNotIn(forbidden, rendered)
        privacy = snapshot['privacy']
        for key, value in privacy.items():
            self.assertFalse(value, key)

    def test_empty_and_unavailable_states_are_truthful(self):
        empty = MODULE.build_snapshot(
            ruleset_document={'nftables': []},
            ruleset_error=None,
            service={'LoadState': 'loaded', 'Result': 'success', 'ExecMainStatus': '0'},
        )
        self.assertEqual(empty['observation']['state'], 'empty')
        self.assertTrue(empty['observation']['observed'])
        unavailable = MODULE.build_snapshot(
            ruleset_document=None,
            ruleset_error='nft ruleset query is unavailable',
            service={},
        )
        self.assertEqual(unavailable['observation']['state'], 'unavailable')
        self.assertFalse(unavailable['observation']['observed'])
        not_installed = MODULE.build_snapshot(
            ruleset_document=None,
            ruleset_error='nft command is not installed',
            service={},
        )
        self.assertEqual(not_installed['observation']['state'], 'not_installed')

    def test_live_collection_uses_only_read_commands(self):
        calls = []

        def runner(args):
            calls.append(list(args))
            if args[0].endswith('/nft'):
                return subprocess.CompletedProcess(args, 0, json.dumps(sample_ruleset()), '')
            return subprocess.CompletedProcess(
                args, 0,
                'LoadState=loaded\nActiveState=active\nSubState=exited\nUnitFileState=enabled\nResult=success\nExecMainStatus=0\n',
                '',
            )

        snapshot = MODULE.collect_live_state(
            nft_path=pathlib.Path('/usr/sbin/nft'),
            systemctl_path=pathlib.Path('/usr/bin/systemctl'),
            runner=runner,
        )
        self.assertEqual(snapshot['observation']['state'], 'ruleset_observed')
        self.assertEqual(calls[0], ['/usr/sbin/nft', '-j', 'list', 'ruleset'])
        rendered_calls = '\n'.join(' '.join(call) for call in calls).lower()
        for forbidden in (' add ', ' delete ', ' flush ', ' insert ', ' replace ', ' -f ', ' monitor '):
            self.assertNotIn(forbidden, f' {rendered_calls} ')

    def test_atomic_write_is_private(self):
        with tempfile.TemporaryDirectory() as directory:
            output = pathlib.Path(directory) / 'live-state.json'
            snapshot = MODULE.build_snapshot(
                ruleset_document=sample_ruleset(),
                ruleset_error=None,
                service={'LoadState': 'loaded', 'Result': 'success', 'ExecMainStatus': '0'},
            )
            MODULE.write_snapshot(snapshot, output)
            written = json.loads(output.read_text(encoding='utf-8'))
            self.assertEqual(written['contract'], MODULE.CONTRACT)
            self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o640)


if __name__ == '__main__':
    unittest.main()
