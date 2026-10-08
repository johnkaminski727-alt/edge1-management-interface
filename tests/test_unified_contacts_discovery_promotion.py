import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import server.edge1_operations_typed_actions as actions
from tools.unified_contacts.schema_v1 import migrate as migrate_v1
from tools.unified_contacts.schema_contacts_expansion import apply_schema
from tools.unified_contacts.maintenance_bot import open_state, process_mail_contact_candidates


class UnifiedContactsDiscoveryPromotionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.contacts = root / 'contacts.sqlite'
        self.maintenance = root / 'maintenance.sqlite'

        con = sqlite3.connect(self.contacts)
        con.executescript('''
            CREATE TABLE organizations(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL);
            CREATE TABLE phone_numbers(id INTEGER PRIMARY KEY AUTOINCREMENT,normalized_number TEXT NOT NULL UNIQUE);
            CREATE TABLE source_documents(id INTEGER PRIMARY KEY AUTOINCREMENT,document_type TEXT NOT NULL,source_name TEXT NOT NULL);
            CREATE TABLE schema_metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        ''')
        migrate_v1(con)
        apply_schema(con)
        con.commit(); con.close()

        state = open_state(self.maintenance)
        for idx in (1, 2):
            state.execute(
                "INSERT INTO mail_contact_extractions(id,fingerprint,message_id,message_sha256,occurred_at,sender,subject,security_state,reviewed,extracted_at,attachment_count,candidate_count) VALUES(?,?,?,?,?,?,?,?,?,?,0,2)",
                (idx, f'f{idx}', f'<m{idx}>', f'h{idx}', f'2026-10-0{idx}T12:00:00Z', 'info@hartfamilyvet.com', 'Appointment Confirmation from Hart Family Veterinary Clinic', 'released', 0, '2026-10-07T12:00:00Z'),
            )
            state.execute(
                "INSERT INTO mail_contact_candidates(fingerprint,extraction_id,candidate_type,normalized_value,display_value,confidence,source_kind,source_reference,context,status,created_at) VALUES(?,?,?,?,?,?,?,?,?,'queued_review','now')",
                (f'e{idx}', idx, 'email', 'info@hartfamilyvet.com', 'info@hartfamilyvet.com', 'high', 'message_header', 'sender', 'info@hartfamilyvet.com'),
            )
            state.execute(
                "INSERT INTO mail_contact_candidates(fingerprint,extraction_id,candidate_type,normalized_value,display_value,confidence,source_kind,source_reference,context,status,created_at) VALUES(?,?,?,?,?,?,?,?,?,'queued_review','now')",
                (f'p{idx}', idx, 'phone', '2509627808', '250-962-7808', 'medium', 'message_body', 'body', 'Phone 250-962-7808'),
            )
        src = sqlite3.connect(self.contacts)
        src.row_factory = sqlite3.Row
        process_mail_contact_candidates(src, state)
        state.commit(); src.close(); state.close()

        self.old_contacts = actions.CONTACTS_DB
        self.old_maintenance = actions.CONTACTS_MAINTENANCE_DB
        actions.CONTACTS_DB = self.contacts
        actions.CONTACTS_MAINTENANCE_DB = self.maintenance

    def tearDown(self):
        actions.CONTACTS_DB = self.old_contacts
        actions.CONTACTS_MAINTENANCE_DB = self.old_maintenance
        self.tmp.cleanup()

    def test_promotion_creates_one_entity_points_and_mail_provenance(self):
        result = actions.contacts_discovery_promote({
            'discovery_id': 1,
            'entity_type': 'organization',
            'canonical_name': 'Hart Family Veterinary Clinic',
            'idempotency_key': 'discovery-promote-test-0001',
        })
        self.assertTrue(result['entity_created'])
        self.assertEqual(result['contact_points_promoted'], 2)
        self.assertEqual(result['provenance_records'], 2)

        con = sqlite3.connect(self.contacts)
        con.row_factory = sqlite3.Row
        entity = con.execute("SELECT id,canonical_name FROM contact_entities WHERE canonical_name='Hart Family Veterinary Clinic'").fetchone()
        self.assertIsNotNone(entity)
        self.assertEqual(con.execute('SELECT COUNT(*) FROM contact_assertions WHERE entity_id=?',(entity['id'],)).fetchone()[0], 2)
        self.assertEqual(con.execute("SELECT COUNT(*) FROM provenance_records WHERE extraction_method='contact_discovery_promotion'").fetchone()[0], 2)
        self.assertEqual(con.execute('SELECT COUNT(*) FROM assertion_evidence').fetchone()[0], 4)
        self.assertEqual(con.execute("SELECT COUNT(*) FROM contact_observations WHERE observation_type='email_occurrence'").fetchone()[0], 2)
        self.assertEqual(con.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
        self.assertEqual(con.execute('PRAGMA foreign_key_check').fetchall(), [])
        con.close()

        maint = sqlite3.connect(self.maintenance)
        row = maint.execute('SELECT status,matched_entity_id FROM contact_discovery_queue WHERE id=1').fetchone()
        self.assertEqual(row[0], 'promoted')
        self.assertEqual(row[1], entity['id'])
        maint.close()

        replay = actions.contacts_discovery_promote({
            'discovery_id': 1,
            'entity_type': 'organization',
            'canonical_name': 'Hart Family Veterinary Clinic',
            'idempotency_key': 'discovery-promote-test-0002',
        })
        self.assertTrue(replay['already_promoted'])
        self.assertEqual(replay['entity_id'], entity['id'])

    def test_invalid_secondary_phone_does_not_block_verified_identity(self):
        maint = sqlite3.connect(self.maintenance)
        row = maint.execute(
            'SELECT evidence_json FROM contact_discovery_queue WHERE id=1'
        ).fetchone()
        evidence = json.loads(row[0])
        evidence['coordinates'].append({
            'candidate_id': 999,
            'type': 'phone',
            'value': 'not-a-phone',
            'display': 'not-a-phone',
            'confidence': 'medium',
            'source_kind': 'message_body',
            'source_reference': 'body',
        })
        maint.execute(
            'UPDATE contact_discovery_queue SET evidence_json=? WHERE id=1',
            (json.dumps(evidence),),
        )
        maint.commit(); maint.close()

        result = actions.contacts_discovery_promote({
            'discovery_id': 1,
            'entity_type': 'organization',
            'canonical_name': 'Hart Family Veterinary Clinic',
            'idempotency_key': 'discovery-promote-test-invalid-phone',
        })
        self.assertTrue(result['entity_created'])
        self.assertEqual(result['contact_points_promoted'], 2)


if __name__ == '__main__':
    unittest.main()
