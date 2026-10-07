import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from server.unified_contacts_maintenance import UnifiedContactsMaintenance


class UnifiedContactsMaintenanceReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.maintenance = root / "maintenance.sqlite"
        self.contacts = root / "contacts.sqlite"

        con = sqlite3.connect(self.contacts)
        con.executescript('''
            CREATE TABLE contact_entities(
              id INTEGER PRIMARY KEY,
              entity_type TEXT NOT NULL,
              canonical_name TEXT NOT NULL,
              display_name TEXT,
              lifecycle_status TEXT NOT NULL
            );
            INSERT INTO contact_entities VALUES(7,'organization','Example Org','Example Org','active');
        ''')
        con.commit(); con.close()

        con = sqlite3.connect(self.maintenance)
        con.executescript('''
            CREATE TABLE maintenance_runs(id INTEGER PRIMARY KEY,started_at TEXT,finished_at TEXT,status TEXT,summary_json TEXT);
            CREATE TABLE maintenance_findings(id INTEGER PRIMARY KEY,finding_type TEXT,severity TEXT,action_level TEXT,entity_id INTEGER,contact_point_id INTEGER,title TEXT,detail TEXT,status TEXT,first_seen_at TEXT,last_seen_at TEXT,occurrences INTEGER);
            CREATE TABLE enrichment_queue(id INTEGER PRIMARY KEY,entity_id INTEGER,task_type TEXT,rationale TEXT,status TEXT,created_at TEXT,updated_at TEXT);
            CREATE TABLE candidate_changes(id INTEGER PRIMARY KEY,action_level TEXT,entity_id INTEGER,contact_point_id INTEGER,target_table TEXT,target_field TEXT,current_value TEXT,proposed_value TEXT,rationale TEXT,status TEXT,created_at TEXT,updated_at TEXT);
            CREATE TABLE identity_resolution_queue(id INTEGER PRIMARY KEY,contact_point_id INTEGER,resolution_kind TEXT,normalized_value TEXT,status TEXT,rationale TEXT,matched_entity_id INTEGER,proposed_entity_name TEXT,confidence TEXT,evidence_json TEXT,created_at TEXT,updated_at TEXT);
            CREATE TABLE contact_discovery_queue(id INTEGER PRIMARY KEY,fingerprint TEXT,sender_email TEXT,sender_domain TEXT,proposed_entity_name TEXT,message_count INTEGER,evidence_json TEXT,status TEXT,matched_entity_id INTEGER,created_at TEXT,updated_at TEXT);
            CREATE TABLE relationship_suggestion_queue(id INTEGER PRIMARY KEY,fingerprint TEXT,discovery_id INTEGER,proposed_person_name TEXT,sender_email TEXT,organization_entity_id INTEGER,relationship_type TEXT,confidence TEXT,rationale TEXT,evidence_json TEXT,status TEXT,created_at TEXT,updated_at TEXT);
            INSERT INTO maintenance_runs VALUES(1,'2026-10-07T10:00:00Z','2026-10-07T10:01:00Z','ok','{}');
            INSERT INTO maintenance_findings VALUES(1,'duplicate_entity','medium','REVIEW_REQUIRED',7,NULL,'Possible duplicate','Review identity','open','2026-10-07','2026-10-07',2);
            INSERT INTO enrichment_queue VALUES(1,7,'missing_address','Find an address','pending','2026-10-07','2026-10-07');
            INSERT INTO candidate_changes VALUES(1,'AUTO_STAGE',7,NULL,'contact_entities','display_name','Example Org','Example Organization','Strong source','pending','2026-10-07','2026-10-07');
            INSERT INTO identity_resolution_queue VALUES(1,99,'phone_identity','+13065550123','pending','Resolve naked phone',NULL,'Example New Contact','probable','{}','2026-10-07','2026-10-07');
            INSERT INTO contact_discovery_queue VALUES(1,'d','info@example.com','example.com','Example Clinic',4,'{"coordinates":[]}','pending',NULL,'2026-10-07','2026-10-07');
            INSERT INTO relationship_suggestion_queue VALUES(1,'r',1,'Jane Example','jane.example@example.com',7,'works_for','probable','Unique organization/domain match','{}','pending','2026-10-07','2026-10-07');
        ''')
        con.commit(); con.close()

        self.model = UnifiedContactsMaintenance(self.maintenance, self.contacts)

    def tearDown(self):
        self.tmp.cleanup()

    def test_summary_reports_operator_queues(self):
        summary = self.model.summary()
        self.assertEqual(summary['open_findings'], 1)
        self.assertEqual(summary['pending_candidates'], 1)
        self.assertEqual(summary['pending_enrichment'], 1)
        self.assertEqual(summary['pending_identity_resolution'], 1)
        self.assertEqual(summary['pending_discoveries'], 1)
        self.assertEqual(summary['pending_relationship_suggestions'], 1)
        self.assertEqual(summary['review_required_findings'], 1)

    def test_items_join_contact_names_and_identity_jobs(self):
        rows = self.model.items(kind='all', status='pending')
        kinds = {row['maintenance_kind'] for row in rows}
        self.assertEqual(kinds, {'finding','enrichment','candidate','identity','discovery','relationship_suggestion'})
        finding = next(row for row in rows if row['maintenance_kind'] == 'finding')
        self.assertEqual(finding['entity_name'], 'Example Org')
        identity = next(row for row in rows if row['maintenance_kind'] == 'identity')
        self.assertEqual(identity['normalized_value'], '+13065550123')
        self.assertEqual(identity['proposed_entity_name'], 'Example New Contact')

    def test_query_filters_identity_resolution(self):
        rows = self.model.items(kind='identity', status='pending', query='5550123')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['maintenance_kind'], 'identity')

    def test_wireless_prefix_metadata_lowers_pending_identity_priority(self):
        triage = Path(self.tmp.name) / "phone-prefix-triage.json"
        triage.write_text(json.dumps({
            "prefixes": {
                "+1306621": {
                    "routing_class": "wireless",
                    "exchange_area": "Yorkton, SK",
                    "carrier": "SaskTel Mobility",
                    "source": "CNAC test fixture"
                }
            }
        }))
        con = sqlite3.connect(self.maintenance)
        con.execute("UPDATE identity_resolution_queue SET normalized_value='+13066211234', evidence_json='{\"occurrence_count\":50,\"source_document_count\":10,\"recovered_source_document_count\":2,\"source_family_count\":1}' WHERE id=1")
        con.commit(); con.close()
        model = UnifiedContactsMaintenance(self.maintenance, self.contacts, triage)
        row = model.items(kind='identity', status='pending')[0]
        self.assertEqual(row['routing_class'], 'wireless')
        self.assertEqual(row['routing_carrier'], 'SaskTel Mobility')
        self.assertEqual(row['routing_exchange_area'], 'Yorkton, SK')
        self.assertLess(row['review_priority'], 100)

    def test_discovery_suggests_unique_existing_organization_from_domain(self):
        con = sqlite3.connect(self.contacts)
        con.execute("INSERT INTO contact_entities VALUES(8,'organization','ClaimsPro LP','ClaimsPro LP','active')")
        con.commit(); con.close()
        con = sqlite3.connect(self.maintenance)
        con.execute("INSERT INTO contact_discovery_queue VALUES(2,'c','denny.vachon@claimspro.ca','claimspro.ca',NULL,8,'{\"coordinates\":[]}','pending',NULL,'2026-10-07','2026-10-07')")
        con.commit(); con.close()
        rows = self.model.items(kind='discoveries', status='pending', query='claimspro')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['suggested_entity_id'], 8)
        self.assertEqual(rows[0]['suggested_entity_name'], 'ClaimsPro LP')
        self.assertIn('sender domain', rows[0]['suggestion_reason'])


if __name__ == '__main__':
    unittest.main()
