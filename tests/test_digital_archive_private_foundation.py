import importlib.util
import json
import pathlib
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).parents[1]
SCRIPT = ROOT / 'deploy/digital-archive/edge1_private_foundation.py'
spec = importlib.util.spec_from_file_location('da_private', SCRIPT)
da = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(da)

PAPERLESS = '''services:\n  webserver:\n    image: ghcr.io/paperless-ngx/paperless-ngx:3.0.5\n    ports:\n      - "127.0.0.1:8113:8000"\n    environment:\n      PAPERLESS_DBPASS_FILE: /run/secrets/paperless_db_password\n      PAPERLESS_SECRET_KEY_FILE: /run/secrets/paperless_secret_key\n'''
ARCHIVEBOX = '''services:\n  archivebox:\n    image: archivebox/archivebox:0.7.4\n    ports:\n      - "127.0.0.1:8114:8000"\n    environment:\n      PUBLIC_INDEX: "False"\n      PUBLIC_SNAPSHOTS: "False"\n      PUBLIC_ADD_VIEW: "False"\n      SAVE_ARCHIVE_DOT_ORG: "False"\n'''


class DigitalArchivePrivateFoundationTests(unittest.TestCase):
    def fake_repo(self, root: pathlib.Path) -> pathlib.Path:
        repo = root / 'repo'
        paperless = repo / da.PAPERLESS_COMPOSE
        archivebox = repo / da.ARCHIVEBOX_COMPOSE
        paperless.parent.mkdir(parents=True)
        archivebox.parent.mkdir(parents=True)
        paperless.write_text(PAPERLESS, encoding='utf-8')
        archivebox.write_text(ARCHIVEBOX, encoding='utf-8')
        return repo

    def make_secret(self, root: pathlib.Path, name: str) -> pathlib.Path:
        path = root / name
        path.write_bytes(b'x' * 48)
        path.chmod(0o600)
        return path

    def test_compose_policy_accepts_private_pinned_sources(self):
        with tempfile.TemporaryDirectory() as td:
            repo = self.fake_repo(pathlib.Path(td))
            hashes = da.validate_compose_sources(repo)
            self.assertEqual(set(hashes), {'paperless_sha256', 'archivebox_sha256'})

    def test_compose_policy_rejects_public_bind(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            repo = self.fake_repo(root)
            path = repo / da.PAPERLESS_COMPOSE
            path.write_text(PAPERLESS.replace('127.0.0.1:8113', '0.0.0.0:8113'), encoding='utf-8')
            with self.assertRaises(da.FoundationError):
                da.validate_compose_sources(repo)

    def test_compose_policy_rejects_archive_org_submission(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            repo = self.fake_repo(root)
            path = repo / da.ARCHIVEBOX_COMPOSE
            path.write_text(ARCHIVEBOX.replace('SAVE_ARCHIVE_DOT_ORG: "False"', 'SAVE_ARCHIVE_DOT_ORG: "True"'), encoding='utf-8')
            with self.assertRaises(da.FoundationError):
                da.validate_compose_sources(repo)

    def test_secret_status_requires_regular_private_file(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            good = self.make_secret(root, 'good.secret')
            self.assertTrue(da.secret_status(good)['ready'])
            broad = self.make_secret(root, 'broad.secret')
            broad.chmod(0o644)
            self.assertEqual(da.secret_status(broad)['reason'], 'permissions-too-broad')
            link = root / 'link.secret'
            link.symlink_to(good)
            self.assertEqual(da.secret_status(link)['reason'], 'symlink-rejected')

    def test_preflight_is_read_only_and_reports_runtime_blocker(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            repo = self.fake_repo(root)
            db = self.make_secret(root, 'db.secret')
            key = self.make_secret(root, 'key.secret')
            before = sorted(str(p.relative_to(root)) for p in root.rglob('*'))
            with mock.patch.object(da, 'docker_ready', return_value=(False, 'docker-not-installed-or-not-on-path')), \
                 mock.patch.object(da, 'tcp_listener_present', return_value=False):
                info = da.preflight(repo, db, key)
            after = sorted(str(p.relative_to(root)) for p in root.rglob('*'))
            self.assertEqual(info['status'], 'preflight-blocked')
            self.assertIn('docker-not-installed-or-not-on-path', info['blockers'])
            self.assertFalse(info['installs_container_runtime'])
            self.assertFalse(info['public_changes'])
            self.assertEqual(before, after)

    def test_preflight_never_returns_secret_contents(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            repo = self.fake_repo(root)
            secret_value = b'super-secret-value-that-must-not-be-returned-123456'
            db = root / 'db.secret'
            key = root / 'key.secret'
            db.write_bytes(secret_value)
            key.write_bytes(secret_value)
            db.chmod(0o600)
            key.chmod(0o600)
            with mock.patch.object(da, 'docker_ready', return_value=(True, 'ready')), \
                 mock.patch.object(da, 'tcp_listener_present', return_value=False):
                info = da.preflight(repo, db, key)
            encoded = json.dumps(info)
            self.assertNotIn(secret_value.decode(), encoded)
            self.assertNotIn(str(db), encoded)
            self.assertNotIn(str(key), encoded)

    def test_apply_requires_root(self):
        with mock.patch.object(da.os, 'geteuid', return_value=1000):
            with self.assertRaises(da.FoundationError):
                da.apply(da.EXPECTED_REPO, pathlib.Path('/tmp/db'), pathlib.Path('/tmp/key'))

    def test_live_apply_repo_is_fixed(self):
        with tempfile.TemporaryDirectory() as td, mock.patch.object(da.os, 'geteuid', return_value=0):
            with self.assertRaises(da.FoundationError):
                da.apply(pathlib.Path(td), pathlib.Path('/tmp/db'), pathlib.Path('/tmp/key'))

    def test_rollback_path_must_stay_under_evidence_root(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            evidence_root = root / 'evidence'
            evidence_root.mkdir()
            good = evidence_root / 'run-1'
            good.mkdir()
            outside = root / 'run-2'
            outside.mkdir()
            with mock.patch.object(da, 'EVIDENCE_ROOT', evidence_root):
                self.assertEqual(da.bounded_evidence_path(good), good.resolve())
                with self.assertRaises(da.FoundationError):
                    da.bounded_evidence_path(outside)

    def test_source_contains_no_runtime_install_or_public_mutation_authority(self):
        text = SCRIPT.read_text(encoding='utf-8').lower()
        for forbidden in (
            'apt install', 'apt-get install', 'dnf install', 'yum install',
            'certbot', 'iptables', 'nft add', 'ufw ', 'a2ensite', 'a2enmod',
            'docker compose down -v',
        ):
            self.assertNotIn(forbidden, text)
        self.assertNotIn('/var/www/edge1-status', text)
        self.assertIn("'public_changes': false", text)
        self.assertIn("'deletes_volumes': false", text)


if __name__ == '__main__':
    unittest.main()
