import importlib.util
import io
import json
import pathlib
import tarfile
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).parents[1]
SCRIPT = ROOT / 'deploy/digital-archive/backup_restore_acceptance.py'
spec = importlib.util.spec_from_file_location('archive_backup', SCRIPT)
archive_backup = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(archive_backup)


class DigitalArchiveBackupRestoreTests(unittest.TestCase):
    def test_safe_tar_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            source = root / 'source'
            source.mkdir()
            (source / 'record.txt').write_text('archive evidence\n', encoding='utf-8')
            archive = root / 'backup.tar.gz'
            archive_backup.tar_directory(source, archive)
            destination = root / 'restored'
            archive_backup.safe_extract(archive, destination)
            self.assertEqual((destination / 'record.txt').read_text(), 'archive evidence\n')

    def test_tar_traversal_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            archive = root / 'bad.tar.gz'
            with tarfile.open(archive, 'w:gz') as handle:
                member = tarfile.TarInfo('../escape.txt')
                payload = b'nope'
                member.size = len(payload)
                handle.addfile(member, io.BytesIO(payload))
            with self.assertRaises(archive_backup.BackupError):
                archive_backup.safe_extract(archive, root / 'restored')

    def test_manifest_hash_verification_detects_tampering(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            paperless = root / 'paperless-export.tar.gz'
            archivebox = root / 'archivebox-data.tar.gz'
            paperless.write_bytes(b'paperless')
            archivebox.write_bytes(b'archivebox')
            manifest = {
                'schema': archive_backup.MANIFEST_SCHEMA,
                'files': {
                    paperless.name: {'sha256': archive_backup.sha256_file(paperless)},
                    archivebox.name: {'sha256': archive_backup.sha256_file(archivebox)},
                },
            }
            (root / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
            self.assertEqual(archive_backup.load_manifest(root)['schema'], archive_backup.MANIFEST_SCHEMA)
            paperless.write_bytes(b'tampered')
            with self.assertRaises(archive_backup.BackupError):
                archive_backup.load_manifest(root)

    def test_restore_compose_is_internal_no_port_and_version_pinned(self):
        text = archive_backup.restore_compose_text(pathlib.Path('/tmp/restore-test'))
        self.assertNotIn('ports:', text)
        self.assertIn('internal: true', text)
        self.assertEqual(text.count('networks: [restore]'), 3)
        self.assertIn(archive_backup.PAPERLESS_IMAGE, text)
        self.assertIn(archive_backup.POSTGRES_IMAGE, text)
        self.assertIn(archive_backup.VALKEY_IMAGE, text)
        self.assertIn('/restore:ro', text)
        self.assertIn('${RESTORE_DB_PASSWORD}', text)
        self.assertIn('${RESTORE_SECRET_KEY}', text)

    def test_consume_queue_must_be_empty(self):
        with tempfile.TemporaryDirectory() as td:
            consume = pathlib.Path(td) / 'consume'
            consume.mkdir()
            self.assertTrue(archive_backup.consume_queue_empty(consume))
            (consume / 'incoming.pdf').write_bytes(b'pending')
            self.assertFalse(archive_backup.consume_queue_empty(consume))
            with self.assertRaises(archive_backup.BackupError):
                archive_backup.require_consume_quiescent(consume)

    def test_preflight_reports_consume_queue_blocker_without_public_authority(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            repo = root / 'repo'
            repo.mkdir()
            export = root / 'export'
            export.mkdir()
            consume = root / 'consume'
            consume.mkdir()
            (consume / 'pending.pdf').write_bytes(b'pending')
            archivebox = root / 'archivebox'
            archivebox.mkdir()
            secret1 = root / 'db.secret'
            secret2 = root / 'app.secret'
            for secret in (secret1, secret2):
                secret.write_bytes(b'x' * 40)
                secret.chmod(0o600)
            with mock.patch.object(archive_backup, 'docker_ready', return_value=True), \
                 mock.patch.object(archive_backup, 'PAPERLESS_EXPORT_ROOT', export), \
                 mock.patch.object(archive_backup, 'PAPERLESS_CONSUME_ROOT', consume), \
                 mock.patch.object(archive_backup, 'ARCHIVEBOX_DATA_ROOT', archivebox):
                info = archive_backup.preflight(repo, secret1, secret2)
            self.assertEqual(info['status'], 'preflight-blocked')
            self.assertIn('paperless-consume-queue-not-empty', info['blockers'])
            self.assertFalse(info['paperless_consume_queue_empty'])
            self.assertFalse(info['public_changes'])
            self.assertFalse(info['canonical_source_changes'])
            self.assertFalse(info['deletes_backup_data'])
            self.assertFalse(info['off_host_backup_created'])

    def test_cleanup_is_required_for_restore_pass(self):
        self.assertTrue(archive_backup.acceptance_pass(True, True, True))
        self.assertFalse(archive_backup.acceptance_pass(True, True, False))
        self.assertFalse(archive_backup.acceptance_pass(False, True, True))
        self.assertFalse(archive_backup.acceptance_pass(True, False, True))

    def test_restore_acceptance_source_has_no_public_or_backup_deletion_authority(self):
        text = SCRIPT.read_text(encoding='utf-8').lower()
        for forbidden in (
            'certbot', 'a2ensite', 'a2enmod', 'iptables', 'nft add', 'ufw ',
            '/var/www/edge1-status', 'rm -rf', 'shutil.rmtree', 'docker compose down -v',
        ):
            self.assertNotIn(forbidden, text)
        self.assertIn("'production_projects_changed': false", text)
        self.assertIn("'restore_network_external_egress': false", text)
        self.assertIn("'ephemeral_secret_values_recorded': false", text)
        self.assertIn("'off_host_backup_created': false", text)


if __name__ == '__main__':
    unittest.main()
