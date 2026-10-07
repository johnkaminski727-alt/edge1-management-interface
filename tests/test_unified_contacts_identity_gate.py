import sqlite3
import unittest

from tools.unified_contacts.identity_gate import match_entity, normalize_identity_name, require_safe_entity_resolution
from tools.unified_contacts.schema_v1 import migrate as migrate_v1
from tools.unified_contacts.schema_contacts_expansion import apply_schema


class IdentityGateTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:')
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.executescript('''
          CREATE TABLE organizations(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL);
          CREATE TABLE phone_numbers(id INTEGER PRIMARY KEY AUTOINCREMENT,normalized_number TEXT UNIQUE NOT NULL);
          CREATE TABLE source_documents(id INTEGER PRIMARY KEY AUTOINCREMENT,document_type TEXT NOT NULL,source_name TEXT NOT NULL);
          CREATE TABLE schema_metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        ''')
        migrate_v1(self.db); apply_schema(self.db)
        self.db.execute("INSERT INTO contact_entities(entity_type,canonical_name,display_name,verification_status) VALUES('organization','Example & Company','Example & Company','verified')")
        eid=self.db.execute("SELECT id FROM contact_entities WHERE canonical_name='Example & Company'").fetchone()[0]
        self.db.execute("INSERT INTO contact_entity_aliases(entity_id,alias_name,alias_type,confidence) VALUES(?,?,?,?)",(eid,'Example Co.','alternate','confirmed'))
        self.db.execute("INSERT INTO provenance_records(source_kind,source_name,verification_status) VALUES('register','test','document_sourced')")
        pid=self.db.execute("SELECT id FROM provenance_records WHERE source_name='test'").fetchone()[0]
        self.db.execute("INSERT INTO contact_attestations(entity_id,provenance_id,attribute,attested_value,verification_status,source_path) VALUES(?,?,?,?,?,?)",(eid,pid,'source_record_id','rec-123','document_sourced','test:rec-123'))
        self.db.commit()

    def tearDown(self): self.db.close()

    def test_name_normalization(self):
        self.assertEqual(normalize_identity_name('Example & Company'), 'example and company')
        self.assertEqual(normalize_identity_name('EXAMPLE-and-company'), 'example and company')

    def test_exact_normalized_canonical_match_reuses_entity(self):
        result=match_entity(self.db,'organization','Example and Company')
        self.assertEqual(result['status'],'existing')

    def test_alias_match_reuses_entity(self):
        result=match_entity(self.db,'organization','Example Co')
        self.assertEqual(result['status'],'existing')
        self.assertIn('alias',result['basis'])

    def test_source_record_id_reuses_entity(self):
        result=match_entity(self.db,'organization','Completely Different Display Label',source_record_id='rec-123')
        self.assertEqual(result['status'],'existing')
        self.assertEqual(result['basis'],'source_record_id')

    def test_strong_near_match_requires_review(self):
        result=match_entity(self.db,'organization','Example & Compny')
        self.assertEqual(result['status'],'review')
        with self.assertRaises(RuntimeError):
            require_safe_entity_resolution(self.db,'organization','Example & Compny')

    def test_distinct_name_can_be_new(self):
        result=match_entity(self.db,'organization','Entirely Different Organization')
        self.assertEqual(result['status'],'new')


if __name__=='__main__': unittest.main()
