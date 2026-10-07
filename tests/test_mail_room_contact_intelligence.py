import importlib.util
import sqlite3
import tempfile
import unittest
from pathlib import Path

from tools.messaging.mail_room_contact_extract import extract_candidates, norm_phone
from tools.messaging.ava_daily_mail_briefing import action_score, evidence_ref
from tools.unified_contacts.maintenance_bot import open_state, process_mail_contact_candidates


class MailContactIntelligenceTests(unittest.TestCase):
    def test_candidate_extraction_from_message_and_attachment(self):
        body='''Best regards,\nJane Example\nDirector\n+1 (306) 555-1212\njane@example.ca\nhttps://example.ca\nS4P 3Y2'''
        attachments=[{'filename':'vendor.vcf','sha256':'a'*64,'text':'support@example.ca\n306-555-3434','type':'text/vcard'}]
        rows=extract_candidates('Jane Example <jane@example.ca>',body,attachments)
        types={r['type'] for r in rows}
        self.assertIn('email',types); self.assertIn('phone',types); self.assertIn('domain',types); self.assertIn('website',types)
        self.assertEqual(norm_phone('+1 (306) 555-1212'),'+13065551212')
        self.assertTrue(any(r.get('attachment_sha256')=='a'*64 for r in rows))

    def test_briefing_helpers(self):
        self.assertGreater(action_score('Action required: invoice due','Please confirm payment.'),1)
        self.assertEqual(len(evidence_ref('<x@example>')),82)

    def test_maintenance_consumes_mail_candidates_without_auto_mutation(self):
        with tempfile.TemporaryDirectory() as d:
            source=Path(d)/'contacts.sqlite'; state=Path(d)/'maintenance.sqlite'
            src=sqlite3.connect(source); src.row_factory=sqlite3.Row
            src.executescript('''
                CREATE TABLE contact_entities(id INTEGER PRIMARY KEY,entity_type TEXT,canonical_name TEXT,lifecycle_status TEXT,display_name TEXT);
                CREATE TABLE contact_points(id INTEGER PRIMARY KEY,point_type TEXT,normalized_value TEXT,display_value TEXT,lifecycle_status TEXT);
                CREATE TABLE contact_assertions(id INTEGER PRIMARY KEY,entity_id INTEGER,contact_point_id INTEGER);
                INSERT INTO contact_entities VALUES(1,'person','Jane Example','active','Jane Example');
                INSERT INTO contact_points VALUES(10,'email','jane@example.ca','jane@example.ca','active');
                INSERT INTO contact_assertions VALUES(1,1,10);
            ''')
            dst=open_state(state)
            dst.execute("INSERT INTO mail_contact_extractions(fingerprint,message_id,message_sha256,occurred_at,sender,subject,security_state,reviewed,extracted_at,attachment_count,candidate_count) VALUES('f','<m>','h','2026-10-07T00:00:00Z','Jane <jane@example.ca>','Hello','released',0,'2026-10-07T01:00:00Z',0,2)")
            eid=dst.execute('SELECT id FROM mail_contact_extractions').fetchone()[0]
            dst.execute("INSERT INTO mail_contact_candidates(fingerprint,extraction_id,candidate_type,normalized_value,display_value,confidence,source_kind,source_reference,created_at) VALUES('c1',?,'email','jane@example.ca','jane@example.ca','high','message_header','sender','now')",(eid,))
            dst.execute("INSERT INTO mail_contact_candidates(fingerprint,extraction_id,candidate_type,normalized_value,display_value,confidence,source_kind,source_reference,created_at) VALUES('c2',?,'phone','+13065551212','306-555-1212','medium','message_body','body','now')",(eid,))
            stats=process_mail_contact_candidates(src,dst); dst.commit()
            self.assertEqual(stats['matched_existing'],1)
            self.assertEqual(stats['queued_review'],1)
            phone=dst.execute("SELECT status,matched_entity_id FROM mail_contact_candidates WHERE candidate_type='phone'").fetchone()
            self.assertEqual(phone['status'],'queued_review'); self.assertEqual(phone['matched_entity_id'],1)
            self.assertEqual(src.execute('SELECT COUNT(*) FROM contact_points').fetchone()[0],1)
            src.close(); dst.close()


if __name__=='__main__': unittest.main()
