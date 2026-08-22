import importlib.util
import json
import pathlib
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).parents[1]
SCRIPT = ROOT / 'deploy/cookie_monster_edge1_activate.py'
spec = importlib.util.spec_from_file_location('cm_activate', SCRIPT)
cm = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(cm)


class ActivationTests(unittest.TestCase):
    def fake_repo(self, root: pathlib.Path) -> pathlib.Path:
        repo = root / 'repo'
        for rel in (
            'server/cookie_monster_contract.py',
            'server/cookie_monster_dispatch.py',
            'server/cookie_monster_fengus_worker.py',
            'deploy/cookie_monster_runtime_publish.py',
        ):
            path = repo / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('# test\n', encoding='utf-8')
        return repo

    def registry(self, root: pathlib.Path, *, enabled=False, non_production=True, read_only=True, extra=None) -> pathlib.Path:
        path = root / 'etc/datasets.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            'enabled': enabled,
            'non_production': non_production,
            'read_only': read_only,
            'description': 'synthetic test',
        }
        if extra:
            entry.update(extra)
        path.write_text(json.dumps({'schema': cm.REGISTRY_SCHEMA, 'datasets': {cm.DATASET_SLUG: entry}}), encoding='utf-8')
        return path

    def test_registry_rejects_authority_bearing_fields(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            registry = self.registry(root, extra={'path': '/archive'})
            with self.assertRaises(cm.ActivationError):
                cm.load_registry(registry)

    def test_registry_requires_nonproduction_readonly(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            for kwargs in ({'non_production': False}, {'read_only': False}):
                registry = self.registry(root, **kwargs)
                with self.assertRaises(cm.ActivationError):
                    cm.load_registry(registry)

    def test_dataset_state_and_preparation_are_deterministic(self):
        with tempfile.TemporaryDirectory() as td:
            dataset = pathlib.Path(td) / 'alpha-staging'
            dataset.mkdir()
            self.assertEqual(cm.dataset_state(dataset)[0], 'empty')
            expected = cm.prepare_synthetic_dataset(dataset)
            self.assertEqual(expected, cm.expected_source_state())
            state, actual = cm.dataset_state(dataset)
            self.assertEqual(state, 'synthetic-ready')
            self.assertEqual(actual, expected)
            (dataset / 'ascii-brunch.txt').chmod(0o644)
            (dataset / 'ascii-brunch.txt').write_text('tampered\n', encoding='utf-8')
            self.assertEqual(cm.dataset_state(dataset)[0], 'conflict')

    def test_preflight_rejects_enabled_empty_dataset(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            repo = self.fake_repo(root)
            registry = self.registry(root, enabled=True)
            dataset = root / 'alpha-staging'
            dataset.mkdir()
            dataset.chmod(0o555)
            with self.assertRaises(cm.ActivationError):
                cm.preflight(
                    repo=repo,
                    registry_path=registry,
                    dataset_path=dataset,
                    generated_path=root / 'generated',
                    current_state=root / 'current.json',
                    verify_runtime=False,
                )

    def test_preflight_is_readonly_and_accepts_disabled_empty_foundation(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            repo = self.fake_repo(root)
            registry = self.registry(root, enabled=False)
            dataset = root / 'alpha-staging'
            dataset.mkdir()
            dataset.chmod(0o555)
            before = list(root.rglob('*'))
            info = cm.preflight(
                repo=repo,
                registry_path=registry,
                dataset_path=dataset,
                generated_path=root / 'generated',
                current_state=root / 'current.json',
                verify_runtime=False,
            )
            after = list(root.rglob('*'))
            self.assertEqual(info['status'], 'preflight-ok')
            self.assertEqual(info['dataset_state'], 'empty')
            self.assertFalse(info['dataset_enabled'])
            self.assertFalse(info['public_changes'])
            self.assertEqual(info['cockpit_stage'], str(cm.COCKPIT_STAGE_ROOT))
            self.assertEqual(before, after)

    def test_preflight_rejects_writable_staging_directory(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            repo = self.fake_repo(root)
            registry = self.registry(root, enabled=False)
            dataset = root / 'alpha-staging'
            dataset.mkdir(mode=0o755)
            with self.assertRaises(cm.ActivationError):
                cm.preflight(
                    repo=repo, registry_path=registry, dataset_path=dataset,
                    generated_path=root / 'generated', current_state=root / 'current.json',
                    verify_runtime=False,
                )

    def test_mutation_repo_is_fixed(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(cm.ActivationError):
                cm._authorized_mutation_repo(pathlib.Path(td))

    def test_apply_requires_root(self):
        with mock.patch.object(cm.os, 'geteuid', return_value=1000):
            with self.assertRaises(cm.ActivationError):
                cm.apply(pathlib.Path('/tmp/nope'))

    def test_safe_backup_paths_are_bounded(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td) / 'backups'
            root.mkdir()
            good = root / 'wwcx-cookie-monster-alpha-activation-20260822T000000Z-1'
            good.mkdir()
            self.assertEqual(cm._safe_backup_path(good, root), good.resolve())
            publisher = root / 'wwcx-cookie-monster-runtime-20260822T000000Z-2'
            publisher.mkdir()
            self.assertEqual(cm._safe_publisher_backup_path(publisher, root), publisher.resolve())
            outside = pathlib.Path(td) / 'wwcx-cookie-monster-alpha-activation-evil'
            outside.mkdir()
            with self.assertRaises(cm.ActivationError):
                cm._safe_backup_path(outside, root)

    def test_work_request_is_fixed_and_path_free(self):
        asset = 'sha256:' + ('a' * 64)
        request = cm._work_request({'job_id': 'cmjob-' + ('b' * 24)}, {'source_asset_id': asset})
        self.assertEqual(request['operation'], 'text.token-stats')
        encoded = json.dumps(request, sort_keys=True).lower()
        for forbidden in ('/srv/', '/var/', 'http://', 'https://', 'command', 'archive', 'credential'):
            self.assertNotIn(forbidden, encoded)

    def test_work_request_rejects_malformed_sha256(self):
        job = {'job_id': 'cmjob-' + ('b' * 24)}
        for asset in ('sha256:not-hex', 'sha256:' + ('A' * 64), 'sha256:' + ('a' * 63), 'md5:' + ('a' * 64)):
            with self.subTest(asset=asset), self.assertRaises(cm.ActivationError):
                cm._work_request(job, {'source_asset_id': asset})

    def test_cockpit_stage_is_not_public_web_root(self):
        self.assertTrue(str(cm.COCKPIT_STAGE_ROOT).startswith('/var/lib/cookie-monster-alpha/'))
        self.assertFalse(str(cm.COCKPIT_STAGE_ROOT).startswith('/var/www/'))

    def test_live_acceptance_passes_verified_synthetic_state(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            dataset = root / 'dataset'
            generated = root / 'generated'
            dataset.mkdir()
            generated.mkdir()
            source = cm.prepare_synthetic_dataset(dataset)
            records = []
            for name, meta in sorted(source.items()):
                records.append({'source_asset_location': name, 'source_asset_id': 'sha256:' + meta['sha256']})
            status = {
                'schema': cm.STATUS_SCHEMA,
                'summary': {
                    'knowledge_records': len(records),
                    'unique_assets': len({r['source_asset_id'] for r in records}),
                    'duplicate_groups': 1,
                    'unauthorized_source_writes': 0,
                },
                'knowledge_records': records,
            }
            cm.atomic_json(generated / 'status.json', status)
            report = cm.write_live_acceptance(
                generated, dataset, source, cm.dataset_state(dataset)[1],
                {'work_id': 'work-' + ('c' * 24), 'result_hash': 'sha256:' + ('d' * 64)},
            )
            self.assertEqual(report['result'], 'pass')
            self.assertEqual(json.loads((generated / 'acceptance.json').read_text())['result'], 'pass')

    def test_live_acceptance_fails_when_source_mutates(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            dataset = root / 'dataset'
            generated = root / 'generated'
            dataset.mkdir()
            generated.mkdir()
            source_before = cm.prepare_synthetic_dataset(dataset)
            records = [
                {'source_asset_location': name, 'source_asset_id': 'sha256:' + meta['sha256']}
                for name, meta in sorted(source_before.items())
            ]
            status = {
                'schema': cm.STATUS_SCHEMA,
                'summary': {'knowledge_records': len(records), 'unique_assets': 3, 'duplicate_groups': 1, 'unauthorized_source_writes': 0},
                'knowledge_records': records,
            }
            cm.atomic_json(generated / 'status.json', status)
            target = dataset / 'facts.json'
            target.chmod(0o644)
            target.write_text('changed\n', encoding='utf-8')
            with self.assertRaises(cm.ActivationError):
                cm.write_live_acceptance(
                    generated, dataset, source_before, cm.dataset_state(dataset)[1],
                    {'work_id': 'work-' + ('c' * 24), 'result_hash': 'sha256:' + ('d' * 64)},
                )


if __name__ == '__main__':
    unittest.main()
