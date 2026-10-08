import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from tools.unified_contacts.import_airtable_organization_snapshot import import_snapshot
from tools.unified_contacts.schema_v1 import migrate as migrate_v1
from tools.unified_contacts.schema_contacts_expansion import apply_schema


class AirtableOrganizationImportTests(unittest.TestCase):
    def test_imports_only_active_high_or_verified_organizations(self):
        with tempfile.TemporaryDirectory() as td:
            dbp = Path(td) / 'contacts.sqlite'
            db = sqlite3.connect(dbp)
            db.executescript('''
                CREATE TABLE organizations(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL);
                CREATE TABLE phone_numbers(id INTEGER PRIMARY KEY AUTOINCREMENT,normalized_number TEXT NOT NULL UNIQUE);
                CREATE TABLE source_documents(id INTEGER PRIMARY KEY AUTOINCREMENT,document_type TEXT NOT NULL,source_name TEXT NOT NULL);
                CREATE TABLE schema_metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            ''')
            migrate_v1(db)
            apply_schema(db)
            source_id = db.execute("INSERT INTO source_documents(document_type,source_name) VALUES('contact-register','fixture')").lastrowid
            payload = {
                'source': {
                    'source_document_id': source_id,
                    'source_kind': 'register',
                    'source_name': 'Airtable Organizations fixture',
                    'source_reference': 'airtable:test',
                    'extraction_method': 'test_snapshot',
                    'verification_status': 'document_sourced',
                },
                'organizations': [
                    {'source_id':'recA','name':'Verified Org','organization_type':'Company','status':'Active','confidence':'Verified','website':'https://example.com'},
                    {'source_id':'recB','name':'High Org','organization_type':'Government','status':'Active','confidence':'High'},
                    {'source_id':'recC','name':'Low Org','organization_type':'Company','status':'Active','confidence':'Low'},
                    {'source_id':'recD','name':'Archived Org','organization_type':'Company','status':'Archived','confidence':'Verified'},
                ],
            }
            stats = import_snapshot(db, payload)
            db.commit()
            names = {r[0] for r in db.execute("SELECT canonical_name FROM contact_entities")}
            self.assertEqual(names, {'Verified Org', 'High Org'})
            self.assertEqual(stats['organizations_created'], 2)
            self.assertEqual(stats['skipped_unverified'], 1)
            self.assertEqual(stats['skipped_archived'], 1)
            prov = db.execute("SELECT source_document_id FROM provenance_records WHERE source_name='Airtable Organizations fixture'").fetchone()
            self.assertEqual(prov[0], source_id)
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
            self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(), [])
            db.close()


if __name__ == '__main__':
    unittest.main()
