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
        p = root / 'omeka-s'
        for name in ('application', 'config', 'files', 'modules', 'themes'):
            (p / name).mkdir(parents=True, exist_ok=True)
        (p / 'index.php').write_text('<?php\n', encoding='utf-8')
        (p / 'VERSION').write_text('4.2.1\n', encoding='utf-8')
        return p

    def dbini(self, root: pathlib.Path) -> pathlib.Path:
        p = root / 'database.ini'
        p.write_text('user = omeka\npassword = secret-value\ndbname = omeka\nhost = localhost\n', encoding='utf-8')
        p.chmod(0o600)
        return p

    def test_payload_tree_hash_and_version(self):
        with tempfile.TemporaryDirectory() as td:
            p = self.payload(pathlib.Path(td))
            status = om.payload_status(p, None)
            self.assertTrue(status['ready'])
            self.assertTrue(status['version'].startswith('4.2'))
            self.assertRegex(status['tree_sha256'], r'^[a-f0-9]{64}$')

    def test_payload_rejects_symlink(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            p = self.payload(root)
            (p / 'link').symlink_to(root / 'elsewhere')
            self.assertEqual(om.payload_status(p, None)['reason'], 'payload-symlink-rejected')

    def test_database_ini_status_never_returns_values_or_path(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            path = self.dbini(root)
            status = om.database_ini_status(path)
            self.assertTrue(status['ready'])
            encoded = json.dumps(status)
            self.assertNotIn('secret-value', encoded)
            self.assertNotIn(str(path), encoded)

    def test_database_ini_rejects_broad_permissions(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            path = self.dbini(root)
            path.chmod(0o644)
            self.assertEqual(om.database_ini_status(path)['reason'], 'permissions-too-broad')

    def test_preflight_is_readonly_and_keeps_public_boundary_false(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            payload = self.payload(root)
            db = self.dbini(root)
            before = sorted(str(p.relative_to(root)) for p in root.rglob('*'))
            with mock.patch.object(om, 'php_status', return_value={'ready': True}), \
                 mock.patch.object(om, 'thumbnail_status', return_value={'ready': True}), \
                 mock.patch.object(om, 'disk_status', return_value={'ready': True}):
                info = om.preflight(root / 'app', payload, None, db)
            after = sorted(str(p.relative_to(root)) for p in root.rglob('*'))
            self.assertEqual(info['status'], 'preflight-ok')
            self.assertFalse(info['public_changes'])
            self.assertFalse(info['creates_database'])
            self.assertFalse(info['creates_first_admin'])
            self.assertEqual(before, after)

    def test_preflight_reports_rewrite_as_unverified(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            payload = self.payload(root)
            db = self.dbini(root)
            with mock.patch.object(om, 'php_status', return_value={'ready': True}), \
                 mock.patch.object(om, 'thumbnail_status', return_value={'ready': True}), \
                 mock.patch.object(om, 'disk_status', return_value={'ready': True}):
                info = om.preflight(root / 'app', payload, None, db)
            self.assertFalse(info['apache_rewrite']['verified'])
            self.assertFalse(info['public_route_verified'])

    def test_apply_installs_private_release_and_secret_config(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            payload = self.payload(root)
            db = self.dbini(root)
            sha = om.payload_status(payload, None)['tree_sha256']
            app = root / 'app'
            with mock.patch.object(om, 'php_status', return_value={'ready': True}), \
                 mock.patch.object(om, 'thumbnail_status', return_value={'ready': True}), \
                 mock.patch.object(om, 'disk_status', return_value={'ready': True}):
                result = om.apply(app, payload, sha, db)
            self.assertEqual(result['status'], 'private-files-deployed')
            self.assertTrue((app / 'current').is_symlink())
            installed = (app / 'current/config/database.ini').resolve()
            self.assertEqual(installed.stat().st_mode & 0o777, 0o600)
            state = json.loads((pathlib.Path(result['evidence']) / 'deployment-state.json').read_text())
            self.assertFalse(state['database_ini_values_recorded'])
            self.assertFalse(state['public_changes'])

    def test_rollback_only_moves_pointer_and_preserves_release(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            payload = self.payload(root)
            db = self.dbini(root)
            sha = om.payload_status(payload, None)['tree_sha256']
            app = root / 'app'
            with mock.patch.object(om, 'php_status', return_value={'ready': True}), \
                 mock.patch.object(om, 'thumbnail_status', return_value={'ready': True}), \
                 mock.patch.object(om, 'disk_status', return_value={'ready': True}):
                result = om.apply(app, payload, sha, db)
            release = app / 'releases' / sha[:16]
            rolled = om.rollback(app, pathlib.Path(result['evidence']))
            self.assertEqual(rolled['status'], 'rolled-back-pointer')
            self.assertFalse((app / 'current').exists())
            self.assertTrue(release.is_dir())
            self.assertTrue(rolled['database_unchanged'])

    def test_source_has_no_db_creation_admin_or_public_mutation_commands(self):
        text = SCRIPT.read_text(encoding='utf-8').lower()
        for forbidden in ('create database', 'create user', 'certbot', 'a2ensite', 'a2enmod', 'curl http', 'wget http', 'public_html'):
            self.assertNotIn(forbidden, text)
        self.assertIn("'public_changes': false", text)
        self.assertIn("'creates_database': false", text)
        self.assertIn("'creates_first_admin': false", text)


if __name__ == '__main__':
    unittest.main()
