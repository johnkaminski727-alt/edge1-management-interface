import importlib.util
import json
import pathlib
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).parents[1]
SCRIPT = ROOT / 'deploy/digital-archive/omeka/business159_omeka_deploy.py'
spec = importlib.util.spec_from_file_location('omeka_deploy', SCRIPT)
om = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(om)


class OmekaDeployTests(unittest.TestCase):
    def payload(self, root: pathlib.Path) -> pathlib.Path:
        path = root / 'omeka-s'
        for name in ('application', 'config', 'files', 'modules', 'themes'):
            (path / name).mkdir(parents=True, exist_ok=True)
        (path / 'index.php').write_text('<?php\n', encoding='utf-8')
        (path / 'VERSION').write_text('4.2.1\n', encoding='utf-8')
        return path

    def dbini(self, root: pathlib.Path, password: str = 'fixture-value') -> pathlib.Path:
        path = root / 'database.ini'
        settings = [('user', 'omeka'), ('password', password), ('dbname', 'omeka'), ('host', 'localhost')]
        path.write_text(''.join(f'{key} = {value}\n' for key, value in settings), encoding='utf-8')
        path.chmod(0o600)
        return path

    def patch_runtime(self):
        return (
            mock.patch.object(om, 'php_status', return_value={'ready': True}),
            mock.patch.object(om, 'thumbnail_status', return_value={'ready': True}),
            mock.patch.object(om, 'disk_status', return_value={'ready': True}),
        )

    def test_payload_tree_hash_and_version(self):
        with tempfile.TemporaryDirectory() as td:
            status = om.payload_status(self.payload(pathlib.Path(td)), None)
            self.assertTrue(status['ready'])
            self.assertTrue(status['version'].startswith('4.2'))
            self.assertRegex(status['tree_sha256'], r'^[a-f0-9]{64}$')

    def test_payload_rejects_symlink(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            payload = self.payload(root)
            (payload / 'link').symlink_to(root)
            self.assertEqual(om.payload_status(payload, None)['reason'], 'payload-symlink-rejected')

    def test_database_ini_status_never_returns_values_or_path(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            path = self.dbini(root)
            status = om.database_ini_status(path)
            encoded = json.dumps(status)
            self.assertTrue(status['ready'])
            self.assertNotIn('fixture-value', encoded)
            self.assertNotIn(str(path), encoded)

    def test_database_ini_rejects_broad_permissions(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            path = self.dbini(root)
            path.chmod(0o644)
            self.assertEqual(om.database_ini_status(path)['reason'], 'permissions-too-broad')

    def test_preflight_is_readonly_and_rewrite_stays_unverified(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            payload = self.payload(root)
            db = self.dbini(root)
            before = sorted(str(path.relative_to(root)) for path in root.rglob('*'))
            php, thumbs, disk = self.patch_runtime()
            with php, thumbs, disk:
                info = om.preflight(root / 'app', payload, None, db)
            after = sorted(str(path.relative_to(root)) for path in root.rglob('*'))
            self.assertEqual(info['status'], 'preflight-ok')
            self.assertFalse(info['public_changes'])
            self.assertFalse(info['creates_database'])
            self.assertFalse(info['creates_first_admin'])
            self.assertFalse(info['apache_rewrite']['verified'])
            self.assertFalse(info['public_route_verified'])
            self.assertEqual(before, after)

    def test_apply_uses_shared_files_and_database_config(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            payload = self.payload(root)
            db = self.dbini(root)
            tree_hash = om.payload_status(payload, None)['tree_sha256']
            app = root / 'app'
            php, thumbs, disk = self.patch_runtime()
            with php, thumbs, disk:
                result = om.apply(app, payload, tree_hash, db)
            current = app / 'current'
            self.assertTrue(current.is_symlink())
            self.assertTrue((current / 'files').is_symlink())
            self.assertEqual((current / 'files').resolve(), (app / 'shared/files').resolve())
            self.assertTrue((current / 'config/database.ini').is_symlink())
            shared_db = app / 'shared/config/database.ini'
            self.assertEqual(shared_db.stat().st_mode & 0o777, 0o600)
            state = json.loads((pathlib.Path(result['evidence']) / 'deployment-state.json').read_text())
            self.assertFalse(state['database_ini_values_recorded'])
            self.assertTrue(state['database_ini_shared'])
            self.assertFalse(state['public_changes'])

    def test_conflicting_shared_database_ini_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            payload = self.payload(root)
            db = self.dbini(root)
            tree_hash = om.payload_status(payload, None)['tree_sha256']
            app = root / 'app'
            php, thumbs, disk = self.patch_runtime()
            with php, thumbs, disk:
                om.apply(app, payload, tree_hash, db)
            changed = self.dbini(root, 'changed-fixture-value')
            php, thumbs, disk = self.patch_runtime()
            with php, thumbs, disk:
                info = om.preflight(app, payload, tree_hash, changed)
            self.assertIn('shared-database-ini-conflict', info['blockers'])

    def test_rollback_moves_pointer_and_preserves_shared_data(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            payload = self.payload(root)
            db = self.dbini(root)
            tree_hash = om.payload_status(payload, None)['tree_sha256']
            app = root / 'app'
            php, thumbs, disk = self.patch_runtime()
            with php, thumbs, disk:
                result = om.apply(app, payload, tree_hash, db)
            release = (app / 'current').resolve()
            rolled = om.rollback(app, pathlib.Path(result['evidence']))
            self.assertEqual(rolled['status'], 'rolled-back-pointer')
            self.assertFalse((app / 'current').exists())
            self.assertTrue(release.is_dir())
            self.assertTrue((app / 'shared/files').is_dir())
            self.assertTrue((app / 'shared/config/database.ini').is_file())
            self.assertTrue(rolled['database_unchanged'])
            self.assertTrue(rolled['persistent_files_preserved'])

    def test_source_has_no_database_admin_or_public_mutation_authority(self):
        text = SCRIPT.read_text(encoding='utf-8').lower()
        for forbidden in (
            'create database', 'create user', 'certbot', 'a2ensite', 'a2enmod',
            'iptables', 'nft add', 'ufw ', 'public_html', 'curl http', 'wget http',
        ):
            self.assertNotIn(forbidden, text)
        self.assertIn("'public_changes': false", text)
        self.assertIn("'creates_database': false", text)
        self.assertIn("'creates_first_admin': false", text)


if __name__ == '__main__':
    unittest.main()
