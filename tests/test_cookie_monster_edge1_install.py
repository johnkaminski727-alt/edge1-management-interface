import importlib.util
import json
import pathlib
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location('cm_install', ROOT / 'deploy/cookie_monster_edge1_install.py')
cm = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(cm)


class InstallTests(unittest.TestCase):
    def layout(self, root):
        repo = root / 'repo'
        (repo / 'config/cookie-monster').mkdir(parents=True)
        (repo / 'deploy').mkdir(exist_ok=True)
        (repo / 'config/cookie-monster/datasets.example.json').write_text(json.dumps({
            'schema': 'wwcx.cookie-monster.datasets.v1',
            'datasets': {'alpha-staging': {
                'enabled': False, 'non_production': True, 'read_only': True, 'description': 'test'
            }}
        }), encoding='utf-8')
        (repo / 'deploy/cookie-monster-fengus-worker@.service').write_text(
            '[Service]\nUser=cookie-monster-fengus\nPrivateNetwork=yes\nProtectSystem=strict\n'
            'InaccessiblePaths=/srv/cookie-monster /var/lib/cookie-monster-alpha/generated\n',
            encoding='utf-8',
        )
        return repo

    def test_preflight_does_not_create_runtime_paths(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            repo = self.layout(root)
            with mock.patch.object(cm.pwd, 'getpwnam', side_effect=KeyError), \
                 mock.patch.object(cm, 'REGISTRY_DEST', root / 'runtime/etc/datasets.json'):
                info = cm.preflight(repo)
            self.assertEqual(info['status'], 'preflight-ok')
            self.assertFalse((root / 'runtime').exists())
            self.assertFalse(info['dataset_enabled'])
            self.assertFalse(info['starts_worker'])

    def test_registry_must_remain_disabled_nonprod_readonly(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            repo = self.layout(root)
            path = repo / 'config/cookie-monster/datasets.example.json'
            value = json.loads(path.read_text())
            value['datasets']['alpha-staging']['enabled'] = True
            path.write_text(json.dumps(value))
            with self.assertRaises(cm.InstallError):
                cm.load_registry(path)

    def test_registry_rejects_authority_fields(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            repo = self.layout(root)
            path = repo / 'config/cookie-monster/datasets.example.json'
            value = json.loads(path.read_text())
            value['datasets']['alpha-staging']['path'] = '/archive'
            path.write_text(json.dumps(value))
            with self.assertRaises(cm.InstallError):
                cm.load_registry(path)

    def test_unit_hardening_is_required(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            repo = self.layout(root)
            (repo / 'deploy/cookie-monster-fengus-worker@.service').write_text('[Service]\nUser=cookie-monster-fengus\n')
            with mock.patch.object(cm, 'REGISTRY_DEST', root / 'etc/datasets.json'):
                with self.assertRaises(cm.InstallError):
                    cm.preflight(repo)

    def test_preflight_reports_existing_registry_conflict(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            repo = self.layout(root)
            destination = root / 'etc/datasets.json'
            destination.parent.mkdir()
            destination.write_text('{"different":true}\n')
            with mock.patch.object(cm, 'REGISTRY_DEST', destination), mock.patch.object(cm.pwd, 'getpwnam', side_effect=KeyError):
                info = cm.preflight(repo)
            self.assertTrue(info['registry_conflict'])

    def test_apply_requires_root(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            repo = self.layout(root)
            with mock.patch.object(cm.os, 'geteuid', return_value=1000):
                with self.assertRaises(cm.InstallError):
                    cm.apply(repo, root / 'backups')

    def test_rollback_requires_root(self):
        with mock.patch.object(cm.os, 'geteuid', return_value=1000):
            with self.assertRaises(cm.InstallError):
                cm.rollback(pathlib.Path('/tmp/nope'))


if __name__ == '__main__':
    unittest.main()
