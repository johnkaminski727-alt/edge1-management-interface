#!/usr/bin/env python3
from __future__ import annotations
import json, tempfile, unittest
from pathlib import Path
from server.ava_office_manager import OfficeManagerStore
from server.ava_office_manager_server import AvaOfficeReadModel
import tools.automation.ava_executive_orchestrator as executive

class AvaExecutiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); root=Path(self.tmp.name)
        self.db=root/'office.sqlite3'; self.inventory=root/'inventory.json'; self.inbox=root/'inbox'; self.status=root/'status.json'
        self.old=(executive.INVENTORY,executive.INBOX,executive.STATUS)
        executive.INVENTORY=self.inventory; executive.INBOX=self.inbox; executive.STATUS=self.status
    def tearDown(self):
        executive.INVENTORY,executive.INBOX,executive.STATUS=self.old; self.tmp.cleanup()
    def inventory_payload(self,state='healthy',stamp='2026-10-08T01:00:00Z'):
        return {'timers':[{'custom':True,'timer':'edge1-example.timer','service':'edge1-example.service','description':'Check example evidence','action_level':'READ-ONLY','last_result':'success','last_run':stamp,'state':'active','enabled':'enabled','next_run':'2026-10-08T02:00:00Z','bot_status':{'slug':'example-evidence','available':True,'state':state,'summary':{'findings':0}}}]}
    def test_team_report_and_assignment_contract(self):
        s=OfficeManagerStore(self.db)
        m=s.upsert_team_member(member_id='example-bot',display_name='Example Bot',department='Records & Library',role='Evidence checker',action_level='READ-ONLY',authority_ceiling='observe',health_state='healthy')
        self.assertEqual(m['department'],'Records & Library')
        r=s.record_team_report(member_id='example-bot',report_type='checkin',health_state='healthy',summary='All clear',detail={'findings':0},source_ref='run:1')
        self.assertTrue(r['new'])
        self.assertFalse(s.record_team_report(member_id='example-bot',report_type='checkin',health_state='healthy',summary='All clear',detail={'findings':0},source_ref='run:1')['new'])
        w=s.create_work_item(title='Review evidence',desired_outcome='Confirm evidence state.',source_channel='ava-executive',owner='ava')
        a=s.create_assignment(member_id='example-bot',objective='Review evidence state.',work_item_id=w['id'])
        self.assertEqual(a['member_id'],'example-bot'); self.assertTrue(s.verify_audit_chain())
    def test_orchestrator_deduplicates_same_bot_run(self):
        self.inventory.write_text(json.dumps(self.inventory_payload()))
        first=executive.run(self.db); second=executive.run(self.db)
        self.assertEqual(first['team_members'],1); self.assertEqual(first['new_reports'],1); self.assertEqual(second['new_reports'],0)
    def test_attention_condition_creates_one_open_work_item(self):
        self.inventory.write_text(json.dumps(self.inventory_payload(state='attention')))
        executive.run(self.db); self.inventory.write_text(json.dumps(self.inventory_payload(state='attention',stamp='2026-10-08T01:30:00Z'))); executive.run(self.db)
        s=OfficeManagerStore(self.db)
        with s.connect() as c:
            self.assertEqual(c.execute("select count(*) from work_items where state not in ('completed','cancelled')").fetchone()[0],1)
            self.assertEqual(c.execute("select count(*) from executive_assignments where state not in ('completed','cancelled')").fetchone()[0],1)
    def test_recovery_closes_attention_work_and_assignment(self):
        self.inventory.write_text(json.dumps(self.inventory_payload(state='attention',stamp='2026-10-08T01:00:00Z'))); executive.run(self.db)
        self.inventory.write_text(json.dumps(self.inventory_payload(state='healthy',stamp='2026-10-08T01:30:00Z'))); executive.run(self.db)
        s=OfficeManagerStore(self.db)
        with s.connect() as c:
            self.assertEqual(c.execute("select count(*) from work_items where state not in ('completed','cancelled')").fetchone()[0],0)
            self.assertEqual(c.execute("select count(*) from executive_assignments where state not in ('completed','cancelled')").fetchone()[0],0)
    def test_read_model_exposes_executive_views(self):
        self.inventory.write_text(json.dumps(self.inventory_payload(state='attention'))); executive.run(self.db)
        r=AvaOfficeReadModel(self.db)
        self.assertEqual(r.executive_summary()['role'],'CEO / Executive Orchestrator')
        self.assertEqual(len(r.team(limit=10)),1); self.assertEqual(len(r.assignments(limit=10)),1); self.assertEqual(len(r.executive_reports(attention_only=True,limit=10)),1)
    def test_edge1_executive_ui_is_read_only(self):
        root=Path(__file__).parents[1]/'src/web/edge1-ops/ava'
        html=(root/'index.html').read_text(); js=(root/'app.js').read_text()
        self.assertIn('Executive orchestrator',html); self.assertIn("AVA's Team",html); self.assertIn('Executive Inbox',html)
        self.assertIn('/edge1-ops/ava-office/api/',js); self.assertNotIn("method:'POST'",js); self.assertNotIn('method: "POST"',js)

if __name__=='__main__': unittest.main()
