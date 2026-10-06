import json
from datetime import date,datetime,timezone
from pathlib import Path
import sqlite3
import tempfile
import unittest
from tools.messaging.mail_room_daily_summary import build,bounds


class DailySummaryTests(unittest.TestCase):
    def test_timezone_boundaries_counts_and_privacy(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root);paths={k:root/(k+'.data') for k in ['auth','outbound','mail','contacts']}
            rows=[{'event_type':'login_succeeded','timestamp':'2026-10-05T05:59:59Z','actor_subject':'private-before','event_id':'before'}, {'event_type':'login_succeeded','timestamp':'2026-10-05T06:00:00Z','actor_subject':'private-user','event_id':'first'}, {'event_type':'login_succeeded','timestamp':'2026-10-05T06:00:00Z','actor_subject':'private-user','event_id':'first'}, {'event_type':'login_failed','timestamp':'2026-10-06T05:59:59Z','actor_subject':'private-user'}, {'event_type':'login_succeeded','timestamp':'2026-10-06T06:00:00Z','actor_subject':'next'}]
            paths['auth'].write_text('\n'.join(json.dumps(r) for r in rows))
            paths['outbound'].write_text(json.dumps({'event':'outbound_message_prepared_api','occurred_at':'2026-10-05T21:00:00Z','recipients':['private@example.test']}))
            with sqlite3.connect(paths['mail']) as db:
                db.execute('CREATE TABLE correspondence (message_id TEXT,source_authoritative INTEGER,source_scope TEXT,direction TEXT,occurred_at TEXT)')
                for scope in ['production_native','synthetic']:db.execute('INSERT INTO correspondence VALUES (?,?,?,?,?)',('<private@example.test>',1,scope,'inbound','2026-10-05T06:00:00Z'))
            with sqlite3.connect(paths['contacts']) as db:
                for table in ['contact_entities','contact_points','contact_relationships']:
                    db.execute('CREATE TABLE '+table+' (created_at TEXT)');db.execute('INSERT INTO '+table+' VALUES (?)',('2026-10-05T06:00:00Z',))
            result=build(date(2026,10,5),paths,datetime(2026,10,6,6,5,tzinfo=timezone.utc))
            self.assertEqual(result['counts']['successful_logins'],1);self.assertEqual(result['counts']['failed_logins'],1);self.assertEqual(result['counts']['messages_sent'],0);self.assertEqual(result['counts']['drafts_prepared'],1);self.assertEqual(result['counts']['messages_received'],1);self.assertEqual(result['counts']['new_contacts'],1)
            self.assertTrue(result['complete_day']);self.assertNotIn('private-user',json.dumps(result));self.assertNotIn('private@example.test',json.dumps(result))
            self.assertEqual(bounds(date(2026,10,5))[0].hour,6)
    def test_missing_is_not_zero_and_today_is_partial(self):
        with tempfile.TemporaryDirectory() as root:
            paths={k:Path(root)/k for k in ['auth','outbound','mail','contacts']}
            result=build(date(2026,10,5),paths,datetime(2026,10,5,21,tzinfo=timezone.utc))
            self.assertFalse(result['complete_day']);self.assertIsNone(result['counts']['messages_sent']);self.assertIsNone(result['counts']['successful_logins']);self.assertEqual(result['sources']['contacts'],'unavailable')

if __name__=='__main__':unittest.main()
