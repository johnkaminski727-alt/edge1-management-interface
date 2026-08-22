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

    def test_restore_compose_is_isolated_and_version_pinned(self):
        text = archive_backup.restore_compose_text(pathlib.Path('/tmp/restore-test'))
        self.assertNotIn('ports:', text)
        self.assertIn(archive_backup.PAPERLESS_IMAGE, text)
        self.assertIn(archive_backup.POSTGRES_IMAGE, text)
        self.assertIn(archive_backup.VALKEY_IMAGE, text)
        self.assertIn('/restore:ro', text)
        self.assertIn('${RESTORE_DB_PASSWORD}', text)
        self.assertIn('${RESTORE_SECRET_KEY}', text)

    def test_preflight_reports_blockers_without_public_authority(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            with mock.patch.object(archive_backup, 'docker_ready', return_value=False), \
                 mock.patch.object(archive_backup, 'PAPERLESS_EXPORT_ROOT', root / 'missing-export'), \
                 mock.patch.object(archive_backup, 'ARCHIVEBOX_DATA_ROOT', root / 'missing-archivebox'):
                info = archive_backup.preflight(root / 'missing-repo')
            self.assertEqual(info['status'], 'preflight-blocked')
            self.assertFalse(info['public_changes'])
            self.assertFalse(info['canonical_source_changes'])
            self.assertFalse(info['deletes_backup_data'])
            self.assertFalse(info['off_host_backup_created'])

    def test_restore_acceptance_source_has_no_public_or_backup_deletion_authority(self):
        text = SCRIPT.read_text(encoding='utf-8').lower()
        for forbidden in (
            'certbot', 'a2ensite', 'a2enmod', 'iptables', 'nft add', 'ufw ',
            '/var/www/edge1-status', 'rm -rf', 'shutil.rmtree', 'docker compose down -v',
        ):
            self.assertNotIn(forbidden, text)
        self.assertIn("'production_projects_changed': false", text)
        self.assertIn("'ephemeral_secret_values_recorded': false", text)
        self.assertIn("'off_host_backup_created': false", text)


if __name__ == '__main__':
    unittest.main()
