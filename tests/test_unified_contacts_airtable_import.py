import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from tools.unified_contacts.schema_v1 import migrate as migrate_v1
from tools.unified_contacts.import_airtable_contact_snapshot import import_snapshot


class AirtableContactImportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / 'contacts.sqlite'
        self.db = sqlite3.connect(self.db_path)
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.executescript('''
            CREATE TABLE organizations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL
            );
            CREATE TABLE phone_numbers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                normalized_number TEXT NOT NULL UNIQUE
            );
            CREATE TABLE source_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_type TEXT NOT NULL,
                source_name TEXT NOT NULL
            );
            CREATE TABLE schema_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        ''')
        migrate_v1(self.db)
        self.payload = {
            'source': {
                'source_kind': 'register',
                'source_name': 'Test Airtable Contacts',
                'source_reference': 'airtable:test/table',
                'verification_status': 'document_sourced',
                'extraction_method': 'test_airtable_snapshot_v1',
            },
            'people': [
                {
                    'source_id': 'rec-test-1',
                    'name': 'Historical Person',
                    'role': 'Former contact',
                    'status': 'Historical',
                    'contact_type': 'Professional',
                    'organization': 'Example Org',
                    'authoritative_source': 'Example register',
                    'last_verified': '2026-01-01',
                },
                {
                    'source_id': 'rec-test-2',
                    'name': 'Restricted Contact',
                    'role': 'Correspondent',
                    'status': 'Do Not Contact',
                    'contact_type': 'Business',
                    'organization': 'Example Org',
                    'authoritative_source': 'Example register',
                    'last_verified': '2026-01-02',
                },
            ],
        }

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_import_is_idempotent_and_preserves_contact_policy(self):
        first = import_snapshot(self.db, self.payload)
        self.db.commit()
        second = import_snapshot(self.db, self.payload)
        self.db.commit()

        self.assertEqual(first['people_created'], 2)
        self.assertEqual(second['people_created'], 0)
        self.assertEqual(second['people_existing'], 2)
        self.assertEqual(
            self.db.execute("SELECT COUNT(*) FROM contact_entities WHERE entity_type='person'").fetchone()[0],
            2,
        )
        dnc = self.db.execute("""
            SELECT COUNT(*) FROM contact_attestations
            WHERE attribute='communication_policy' AND attested_value='do_not_contact'
        """).fetchone()[0]
        self.assertEqual(dnc, 1)
        historical = self.db.execute("""
            SELECT cr.lifecycle_status
            FROM contact_relationships cr
            JOIN contact_entities e ON e.id=cr.left_entity_id
            WHERE e.canonical_name='Historical Person'
        """).fetchone()[0]
        self.assertEqual(historical, 'inactive')
        self.assertEqual(self.db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
        self.assertEqual(self.db.execute('PRAGMA foreign_key_check').fetchall(), [])


if __name__ == '__main__':
    unittest.main()
