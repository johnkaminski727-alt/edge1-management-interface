import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.unified_contacts.maintenance_bot import apply_public_phone_resolutions, apply_safe_fixes, open_source, open_state, run, process_mail_contact_candidates, build_relationship_suggestions, mail_candidate_disposition


SCHEMA = '''
CREATE TABLE contact_entities(
 id INTEGER PRIMARY KEY, entity_type TEXT, canonical_name TEXT, display_name TEXT,
 lifecycle_status TEXT, verification_status TEXT, updated_at TEXT
);
CREATE TABLE contact_points(
 id INTEGER PRIMARY KEY, point_type TEXT, normalized_value TEXT, display_value TEXT,
 classification TEXT, lifecycle_status TEXT, updated_at TEXT
);
CREATE TABLE contact_assertions(id INTEGER PRIMARY KEY, entity_id INTEGER, contact_point_id INTEGER, confidence TEXT DEFAULT 'unverified');
'''


class MaintenanceBotTests(unittest.TestCase):
    def test_findings_and_enrichment_are_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            src = sqlite3.connect(':memory:')
            src.row_factory = sqlite3.Row
            src.executescript(SCHEMA + '''
                INSERT INTO contact_entities VALUES(1,'person','Jane Smith','Jane Smith','active','unverified',NULL);
                INSERT INTO contact_entities VALUES(2,'person','Jane  Smith','Jane Smith','active','unverified',NULL);
                INSERT INTO contact_points VALUES(1,'email','bad-email','bad-email',NULL,'active',NULL);
                INSERT INTO contact_assertions(id,entity_id,contact_point_id) VALUES(1,1,1);
            ''')
            dst = open_state(Path(directory) / 'state.sqlite')
            first = run(src, dst)
            dst.commit()
            second = run(src, dst)
            dst.commit()
            self.assertGreaterEqual(first['open_findings'], 2)
            self.assertEqual(first['open_findings'], second['open_findings'])
            self.assertEqual(
                dst.execute("SELECT COUNT(*) FROM maintenance_findings WHERE finding_type='duplicate_entity'").fetchone()[0], 1
            )
            self.assertGreater(dst.execute("SELECT COUNT(*) FROM enrichment_queue").fetchone()[0], 0)
            self.assertGreater(dst.execute("SELECT COUNT(*) FROM candidate_changes").fetchone()[0], 0)
            src.close()
            dst.close()

    def test_noisy_mail_phone_candidates_are_suppressed_and_old_review_items_resolved(self):
        with tempfile.TemporaryDirectory() as directory:
            src = sqlite3.connect(':memory:')
            src.row_factory = sqlite3.Row
            src.executescript(SCHEMA)
            dst = open_state(Path(directory) / 'state.sqlite')
            dst.execute("INSERT INTO mail_contact_extractions(fingerprint,message_id,message_sha256,occurred_at,sender,subject,security_state,reviewed,extracted_at,attachment_count,candidate_count) VALUES('f','<m>','h','2026-10-07','Apple <noreply@example.com>','Security','released',0,'2026-10-07',0,1)")
            eid = dst.execute('SELECT id FROM mail_contact_extractions').fetchone()[0]
            dst.execute("INSERT INTO mail_contact_candidates(id,fingerprint,extraction_id,candidate_type,normalized_value,display_value,confidence,source_kind,source_reference,context,status,created_at) VALUES(10,'c',?,'phone','4206209230','4.206.209.230','medium','message_body','body','IP address: 4.206.209.230','queued_review','now')", (eid,))
            detail='{"representative_candidate_id":10,"type":"phone","value":"4206209230"}'
            dst.execute("INSERT INTO maintenance_findings(fingerprint,finding_type,severity,action_level,title,detail,status,first_seen_at,last_seen_at) VALUES('mf','mail_contact_candidate','medium','REVIEW_REQUIRED','Mail-derived contact candidate',?,'open','now','now')", (detail,))
            dst.execute("INSERT INTO candidate_changes(fingerprint,action_level,target_table,target_field,current_value,proposed_value,rationale,status,created_at,updated_at) VALUES('cc','REVIEW_REQUIRED','mail_contact_candidates','candidate_review',NULL,?,'review','pending','now','now')", (detail,))
            stats = process_mail_contact_candidates(src, dst)
            dst.commit()
            self.assertEqual(stats['rejected_noise'], 1)
            self.assertEqual(dst.execute("SELECT status FROM mail_contact_candidates WHERE id=10").fetchone()[0], 'rejected_noise')
            self.assertEqual(dst.execute("SELECT status FROM maintenance_findings WHERE fingerprint='mf'").fetchone()[0], 'resolved')
            self.assertEqual(dst.execute("SELECT status FROM candidate_changes WHERE fingerprint='cc'").fetchone()[0], 'superseded')
            src.close(); dst.close()

    def test_strong_shared_contact_point_is_not_treated_as_conflict(self):
        with tempfile.TemporaryDirectory() as directory:
            src = sqlite3.connect(':memory:')
            src.row_factory = sqlite3.Row
            src.executescript(SCHEMA + '''
                INSERT INTO contact_entities VALUES(1,'person','Jane Example','Jane Example','active','verified',NULL);
                INSERT INTO contact_entities VALUES(2,'organization','Example Co','Example Co','active','verified',NULL);
                INSERT INTO contact_points VALUES(1,'email','jane@example.com','jane@example.com',NULL,'active',NULL);
                INSERT INTO contact_assertions VALUES(1,1,1,'confirmed');
                INSERT INTO contact_assertions VALUES(2,2,1,'document_sourced');
            ''')
            dst = open_state(Path(directory) / 'state.sqlite')
            run(src, dst); dst.commit()
            self.assertEqual(dst.execute("SELECT COUNT(*) FROM maintenance_findings WHERE finding_type='shared_contact_point' AND status='open'").fetchone()[0], 0)
            src.close(); dst.close()

    def test_repeated_business_sender_with_phone_becomes_discovery_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            src = sqlite3.connect(':memory:')
            src.row_factory = sqlite3.Row
            src.executescript(SCHEMA)
            dst = open_state(Path(directory) / 'state.sqlite')
            for idx in (1, 2):
                dst.execute("INSERT INTO mail_contact_extractions(id,fingerprint,message_id,message_sha256,occurred_at,sender,subject,security_state,reviewed,extracted_at,attachment_count,candidate_count) VALUES(?,?,?,?,?,?,?,?,?,?,0,2)", (idx,f'f{idx}',f'<m{idx}>',f'h{idx}',f'2026-10-0{idx}', 'info@hartfamilyvet.com','Appointment Confirmation from Hart Family Veterinary Clinic','released',0,'2026-10-07'))
                dst.execute("INSERT INTO mail_contact_candidates(fingerprint,extraction_id,candidate_type,normalized_value,display_value,confidence,source_kind,source_reference,context,status,created_at) VALUES(?,?,?,?,?,?,?,?,?,'queued_review','now')", (f'e{idx}',idx,'email','info@hartfamilyvet.com','info@hartfamilyvet.com','high','message_header','sender','info@hartfamilyvet.com'))
                dst.execute("INSERT INTO mail_contact_candidates(fingerprint,extraction_id,candidate_type,normalized_value,display_value,confidence,source_kind,source_reference,context,status,created_at) VALUES(?,?,?,?,?,?,?,?,?,'queued_review','now')", (f'p{idx}',idx,'phone','+12509627808','250-962-7808','medium','message_body','body','call 250-962-7808'))
            stats = process_mail_contact_candidates(src, dst)
            dst.commit()
            self.assertEqual(stats['discoveries'], 1)
            row = dst.execute("SELECT sender_email,proposed_entity_name,message_count,status FROM contact_discovery_queue").fetchone()
            self.assertEqual(row['sender_email'], 'info@hartfamilyvet.com')
            self.assertEqual(row['proposed_entity_name'], 'Hart Family Veterinary Clinic')
            self.assertEqual(row['message_count'], 2)
            self.assertEqual(row['status'], 'pending')
            self.assertEqual(dst.execute("SELECT COUNT(*) FROM mail_contact_candidates WHERE status='bundled_review'").fetchone()[0], 4)
            src.close(); dst.close()

    def test_legacy_unresolved_phone_enters_identity_resolution_by_observation_count(self):
        with tempfile.TemporaryDirectory() as directory:
            src = sqlite3.connect(':memory:')
            src.row_factory = sqlite3.Row
            src.executescript(SCHEMA + """
                ALTER TABLE contact_points ADD COLUMN legacy_phone_number_id INTEGER;
                CREATE TABLE phone_numbers(id INTEGER PRIMARY KEY,status TEXT,occurrence_count INTEGER);
                INSERT INTO phone_numbers VALUES(10,'unresolved',362);
                INSERT INTO contact_points(id,point_type,normalized_value,display_value,classification,lifecycle_status,updated_at,legacy_phone_number_id) VALUES(10,'phone','+13065550199','(306) 555-0199',NULL,'unknown',NULL,10);
            """)
            dst = open_state(Path(directory) / 'state.sqlite')
            run(src, dst); dst.commit()
            row = dst.execute("SELECT contact_point_id,resolution_kind,normalized_value,status,confidence,evidence_json FROM identity_resolution_queue WHERE contact_point_id=10").fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row['status'], 'pending')
            self.assertEqual(row['confidence'], 'observed')
            self.assertIn('362', row['evidence_json'])
            self.assertEqual(src.execute('SELECT COUNT(*) FROM contact_assertions WHERE contact_point_id=10').fetchone()[0], 0)
            src.close(); dst.close()

    def test_unassigned_role_mailbox_is_staged_to_dominant_existing_org(self):
        with tempfile.TemporaryDirectory() as directory:
            src = sqlite3.connect(':memory:')
            src.row_factory = sqlite3.Row
            src.executescript(SCHEMA + """
                INSERT INTO contact_entities VALUES(1,'organization','Example Communications','Example Communications','active','verified',NULL);
                INSERT INTO contact_entities VALUES(2,'organization','Example Holding','Example Holding','active','verified',NULL);
                INSERT INTO contact_points VALUES(1,'email','contact@example.ca','contact@example.ca',NULL,'active',NULL);
                INSERT INTO contact_points VALUES(2,'email','support@example.ca','support@example.ca',NULL,'active',NULL);
                INSERT INTO contact_points VALUES(3,'email','owner@example.ca','owner@example.ca',NULL,'active',NULL);
                INSERT INTO contact_points VALUES(4,'email','billing@example.ca','billing@example.ca',NULL,'active',NULL);
                INSERT INTO contact_assertions VALUES(1,1,1,'confirmed');
                INSERT INTO contact_assertions VALUES(2,1,2,'document_sourced');
                INSERT INTO contact_assertions VALUES(3,2,3,'confirmed');
            """)
            dst = open_state(Path(directory) / 'state.sqlite')
            run(src, dst); dst.commit()
            row = dst.execute("SELECT entity_id,contact_point_id,proposed_value,status FROM candidate_changes WHERE target_table='contact_assertions' AND contact_point_id=4 AND status='pending'").fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row['entity_id'], 1)
            self.assertEqual(row['proposed_value'], '1')
            src.close(); dst.close()

    def test_machine_and_commissioning_header_senders_are_informational(self):
        for value in ('payments-noreply@google.com','workspace_noreply@google.com','precutover@spiritcreekgardens.com','mail-gateway-acceptance@ww.cx','canary@example.net'):
            row={'candidate_type':'email','normalized_value':value,'display_value':value,'context':'','source_kind':'message_header'}
            self.assertEqual(mail_candidate_disposition(row),'informational_only',value)
        human={'candidate_type':'email','normalized_value':'notices@parklandlibrary.ca','display_value':'notices@parklandlibrary.ca','context':'','source_kind':'message_header'}
        self.assertIsNone(mail_candidate_disposition(human))

    def test_low_value_mail_candidates_leave_active_review_without_losing_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            src = sqlite3.connect(':memory:')
            src.row_factory = sqlite3.Row
            src.executescript(SCHEMA)
            dst = open_state(Path(directory) / 'state.sqlite')
            dst.execute("INSERT INTO mail_contact_extractions(fingerprint,message_id,message_sha256,occurred_at,sender,subject,security_state,reviewed,extracted_at,attachment_count,candidate_count) VALUES('f2','<m2>','h2','2026-10-07','noreply@google.com','Security','released',0,'2026-10-07',0,5)")
            eid = dst.execute('SELECT id FROM mail_contact_extractions').fetchone()[0]
            rows = [
                (20,'e1','email','noreply@google.com','noreply@google.com','high','message_header','sender','noreply@google.com'),
                (21,'e2','email','y@ww.cx','y@ww.cx','medium','message_body','body','account da**y@ww.cx'),
                (22,'j1','job_title','apple support','Apple Support','low','message_body','body','Apple Support'),
                (23,'a1','postal_address','L5N 0B9','L5N 0B9','low','message_body','body','L5N 0B9'),
                (24,'p1','phone','+13065551212','+1 (306) 555-1212','medium','message_body','body','Phone +1 (306) 555-1212'),
            ]
            for row in rows:
                dst.execute("INSERT INTO mail_contact_candidates(id,fingerprint,extraction_id,candidate_type,normalized_value,display_value,confidence,source_kind,source_reference,context,status,created_at) VALUES(?,?,?, ?,?,?,?,?,?,?, 'queued_review','now')", (row[0],row[1],eid,*row[2:]))
            stats = process_mail_contact_candidates(src, dst)
            dst.commit()
            self.assertEqual(stats['informational_only'], 3)
            self.assertEqual(stats['rejected_noise'], 1)
            self.assertEqual(dst.execute("SELECT status FROM mail_contact_candidates WHERE id=20").fetchone()[0], 'informational_only')
            self.assertEqual(dst.execute("SELECT status FROM mail_contact_candidates WHERE id=21").fetchone()[0], 'rejected_noise')
            self.assertEqual(dst.execute("SELECT status FROM mail_contact_candidates WHERE id=22").fetchone()[0], 'informational_only')
            self.assertEqual(dst.execute("SELECT status FROM mail_contact_candidates WHERE id=23").fetchone()[0], 'informational_only')
            self.assertEqual(dst.execute("SELECT status FROM mail_contact_candidates WHERE id=24").fetchone()[0], 'queued_review')
            src.close(); dst.close()

    def test_safe_autofix_only_fills_missing_display_fields_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            source_path = Path(directory) / 'contacts.sqlite'
            state_path = Path(directory) / 'state.sqlite'
            backup_dir = Path(directory) / 'backups'
            con = sqlite3.connect(source_path)
            con.executescript(SCHEMA + '''
                INSERT INTO contact_entities VALUES(1,'person','Jane Smith',NULL,'active','verified',NULL);
                INSERT INTO contact_entities VALUES(2,'person','Keep Name','Custom Display','active','verified',NULL);
                INSERT INTO contact_points VALUES(1,'email','jane@example.com',NULL,NULL,'active',NULL);
                INSERT INTO contact_points VALUES(2,'phone','+13065550100','(306) 555-0100',NULL,'active',NULL);
                INSERT INTO contact_points VALUES(3,'phone','+13065550101','(306) 555-0101',NULL,'unknown',NULL);
                INSERT INTO contact_assertions VALUES(3,1,3,'document_sourced');
            ''')
            con.commit()
            con.close()

            dst = open_state(state_path)
            src = open_source(source_path, writable=True)
            first = apply_safe_fixes(src, source_path, dst, 1, backup_dir)
            dst.commit()
            self.assertEqual(first['planned'], 3)
            self.assertEqual(first['applied'], 3)
            self.assertTrue(Path(first['backup']).is_file())
            self.assertEqual(src.execute('SELECT display_name FROM contact_entities WHERE id=1').fetchone()[0], 'Jane Smith')
            self.assertEqual(src.execute('SELECT display_name FROM contact_entities WHERE id=2').fetchone()[0], 'Custom Display')
            self.assertEqual(src.execute('SELECT display_value FROM contact_points WHERE id=1').fetchone()[0], 'jane@example.com')
            self.assertEqual(src.execute('SELECT display_value FROM contact_points WHERE id=2').fetchone()[0], '(306) 555-0100')
            second = apply_safe_fixes(src, source_path, dst, 2, backup_dir)
            self.assertEqual(second['planned'], 0)
            self.assertEqual(second['applied'], 0)
            self.assertEqual(src.execute("SELECT lifecycle_status FROM contact_points WHERE id=3").fetchone()[0], 'active')
            self.assertEqual(dst.execute("SELECT COUNT(*) FROM remediation_actions WHERE action_level='AUTO_FIX'").fetchone()[0], 3)
            src.close()
            dst.close()


    def test_reconciliation_cycle_closes_conditions_that_disappear(self):
        from tools.unified_contacts.maintenance_bot import begin_reconciliation_cycle, finish_reconciliation_cycle
        with tempfile.TemporaryDirectory() as directory:
            dst = open_state(Path(directory) / 'state.sqlite')
            now = '2026-10-07T00:00:00+00:00'
            dst.execute("INSERT INTO maintenance_findings(fingerprint,finding_type,severity,action_level,title,detail,status,first_seen_at,last_seen_at) VALUES('f','duplicate_entity','high','REVIEW_REQUIRED','Duplicate','old','open',?,?)", (now, now))
            dst.execute("INSERT INTO enrichment_queue(fingerprint,entity_id,task_type,rationale,status,created_at,updated_at) VALUES('e',1,'find_email','old','pending',?,?)", (now, now))
            dst.execute("INSERT INTO candidate_changes(fingerprint,action_level,target_table,target_field,rationale,status,created_at,updated_at) VALUES('c','REVIEW_REQUIRED','contact_entities','identity_merge','old','pending',?,?)", (now, now))
            dst.execute("INSERT INTO identity_resolution_queue(fingerprint,contact_point_id,resolution_kind,normalized_value,status,rationale,created_at,updated_at) VALUES('i',10,'reverse_phone','+13065550100','pending','old',?,?)", (now, now))
            begin_reconciliation_cycle(dst)
            finish_reconciliation_cycle(dst)
            self.assertEqual(dst.execute("SELECT status FROM maintenance_findings WHERE fingerprint='f'").fetchone()[0], 'resolved')
            self.assertEqual(dst.execute("SELECT status FROM enrichment_queue WHERE fingerprint='e'").fetchone()[0], 'resolved')
            self.assertEqual(dst.execute("SELECT status FROM candidate_changes WHERE fingerprint='c'").fetchone()[0], 'superseded')
            self.assertEqual(dst.execute("SELECT status FROM identity_resolution_queue WHERE fingerprint='i'").fetchone()[0], 'superseded')
            dst.close()


    def test_known_voicemail_service_number_is_not_queued_for_identity_resolution(self):
        with tempfile.TemporaryDirectory() as directory:
            src = sqlite3.connect(':memory:')
            src.row_factory = sqlite3.Row
            src.executescript(SCHEMA + """
                ALTER TABLE contact_points ADD COLUMN legacy_phone_number_id INTEGER;
                CREATE TABLE phone_numbers(id INTEGER PRIMARY KEY,status TEXT,occurrence_count INTEGER);
                INSERT INTO phone_numbers VALUES(10,'unresolved',122);
                INSERT INTO contact_points(id,point_type,normalized_value,display_value,classification,lifecycle_status,updated_at,legacy_phone_number_id)
                VALUES(10,'phone','+13065804001','(306) 580-4001',NULL,'unknown',NULL,10);
            """)
            dst = open_state(Path(directory) / 'state.sqlite')
            summary = run(src, dst)
            dst.commit()
            self.assertEqual(summary['known_service_numbers_seen'], 1)
            self.assertEqual(dst.execute("SELECT COUNT(*) FROM identity_resolution_queue WHERE contact_point_id=10 AND status='pending'").fetchone()[0], 0)
            src.close(); dst.close()


    def test_public_phone_resolutions_stage_existing_and_new_organization(self):
        with tempfile.TemporaryDirectory() as directory:
            src = sqlite3.connect(':memory:')
            src.row_factory = sqlite3.Row
            src.executescript(SCHEMA + """
                INSERT INTO contact_entities VALUES(76,'organization','Crossroads Credit Union','Crossroads Credit Union','active','document_sourced',NULL);
                INSERT INTO contact_points VALUES(31,'phone','+13065635641','306-563-5641',NULL,'unknown',NULL);
                INSERT INTO contact_points VALUES(43,'phone','+13065471555','306-547-1555',NULL,'unknown',NULL);
            """)
            dst = open_state(Path(directory) / 'state.sqlite')
            now = '2026-10-07T00:00:00+00:00'
            for point_id, number in ((31,'+13065635641'),(43,'+13065471555')):
                dst.execute("INSERT INTO identity_resolution_queue(fingerprint,contact_point_id,resolution_kind,normalized_value,status,rationale,created_at,updated_at) VALUES(?,?, 'reverse_phone',?,'pending','test',?,?)", (f'i{point_id}',point_id,number,now,now))
            fixture = {
                '+13065635641': {
                    'normalized_number': '+13065635641', 'resolution': 'existing_organization',
                    'canonical_name': 'Crossroads Credit Union', 'confidence': 'document_sourced',
                    'rationale': 'verified public source', 'sources': [{'url':'https://example.test/crossroads'}],
                },
                '+13065471555': {
                    'normalized_number': '+13065471555', 'resolution': 'new_organization',
                    'canonical_name': 'Preeceville Dental', 'confidence': 'document_sourced',
                    'rationale': 'verified public source', 'sources': [{'url':'https://example.test/dental'}],
                    'contact_points': [{'point_type':'website','value':'https://preecevilledental.ca'}],
                },
            }
            with patch('tools.unified_contacts.maintenance_bot.load_public_phone_resolutions', return_value=fixture):
                stats = apply_public_phone_resolutions(src, dst)
            dst.commit()
            self.assertEqual(stats['matched_existing'], 1)
            self.assertEqual(stats['new_organization_candidates'], 1)
            existing = dst.execute("SELECT status,matched_entity_id,proposed_entity_name FROM identity_resolution_queue WHERE contact_point_id=31").fetchone()
            self.assertEqual((existing['status'], existing['matched_entity_id'], existing['proposed_entity_name']), ('matched_existing',76,'Crossroads Credit Union'))
            new = dst.execute("SELECT status,proposed_entity_name FROM identity_resolution_queue WHERE contact_point_id=43").fetchone()
            self.assertEqual((new['status'],new['proposed_entity_name']), ('review_required','Preeceville Dental'))
            self.assertEqual(dst.execute("SELECT COUNT(*) FROM candidate_changes WHERE target_table='contact_assertions' AND status='pending'").fetchone()[0], 1)
            self.assertEqual(dst.execute("SELECT COUNT(*) FROM candidate_changes WHERE target_table='contact_entities' AND target_field='create_from_phone_resolution' AND status='pending'").fetchone()[0], 1)
            src.close(); dst.close()


if __name__ == '__main__':
    unittest.main()
