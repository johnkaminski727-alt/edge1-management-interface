import sqlite3
import unittest

from tools.private_library import library_source_catalog as mod


class LibrarySourceCatalogTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.row_factory = sqlite3.Row
        self.db.executescript(mod.SCHEMA)
        self.ts = '2026-10-08T00:00:00+00:00'

    def tearDown(self):
        self.db.close()

    def test_schema_has_accounting_and_catalog_tables(self):
        names = {r[0] for r in self.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertIn('library_sources', names)
        self.assertIn('library_items', names)
        self.assertIn('library_item_domain_state', names)
        self.assertIn('accounting_document_facts', names)
        self.assertIn('accounting_line_items', names)
        self.assertIn('accounting_reconciliation_links', names)

    def test_catalog_source_and_item_create_domain_states(self):
        source = {
            'id': 'dropbox-documents', 'provider': 'dropbox', 'name': 'Dropbox Documents',
            'source_type': 'folder', 'locator': 'ns:1//Documents', 'runtime_access': 'connector_required',
            'enabled': True, 'copy_policy': 'cache', 'classification': 'private', 'sensitivity': 'normal'
        }
        mod.ensure_catalog_source(self.db, source, self.ts)
        item_id = mod.upsert_item(self.db, 'dropbox-documents', 'dropbox', 'id:abc', 'Bill.pdf', self.ts)
        states = {r['domain']: r['state'] for r in self.db.execute('SELECT domain,state FROM library_item_domain_state WHERE item_id=?', (item_id,))}
        self.assertEqual(states, {'contacts': 'pending', 'accounting': 'pending', 'filing': 'pending'})
        row = self.db.execute('SELECT provider,copy_policy,last_status FROM library_sources WHERE id=?', ('dropbox-documents',)).fetchone()
        self.assertEqual(row['provider'], 'dropbox')
        self.assertEqual(row['copy_policy'], 'cache')
        self.assertEqual(row['last_status'], 'deferred')

    def test_google_drive_evidence_maps_to_unique_drive_source(self):
        mod.ensure_catalog_source(self.db, {
            'id': 'google-drive-sasktel-evidence', 'provider': 'google-drive', 'name': 'SaskTel',
            'source_type': 'folder', 'locator': 'gdrive-folder:root', 'runtime_access': 'connector_required',
            'enabled': True, 'copy_policy': 'evidence'
        }, self.ts)
        mod.ensure_source(self.db, {'id':'edge1-evidence-register','name':'Evidence','kind':'edge1_register','locator':'/evidence','runtime_access':'local','ingestion':'enabled'}, self.ts)
        row = {'source_reference': 'gdrive:file123', 'source_name': 'SaskTel Bill.pdf'}
        self.assertEqual(mod.evidence_source_id(self.db, row), 'google-drive-sasktel-evidence')


if __name__ == '__main__':
    unittest.main()
