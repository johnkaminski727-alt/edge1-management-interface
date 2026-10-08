from __future__ import annotations
import json, tempfile, unittest
from pathlib import Path
from unittest import mock

from server.ava_office_manager import OfficeManagerStore
from server.ava_office_manager_server import AvaOfficeReadModel
from tools.automation import ava_operations_intelligence as intel
from server import ava_dispatch_admin

ROOT=Path(__file__).resolve().parents[1]

class AvaOperationsIntelligenceTests(unittest.TestCase):
    def test_office_schema_contains_intelligence_tables(self):
        with tempfile.TemporaryDirectory() as td:
            db=Path(td)/'office.sqlite3'; store=OfficeManagerStore(db)
            with store.connect() as c:
                names={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            for name in ('executive_reviews','executive_briefings','executive_team_metrics','executive_source_health','executive_accounting_completeness','executive_entity_profiles','executive_automation_hygiene','executive_why_events','executive_workflow_templates','executive_automation_lifecycle'):
                self.assertIn(name,names)

    def test_maturity_never_promotes_review_required(self):
        self.assertEqual(intel.maturity('REVIEW-REQUIRED',100,1.0,0)[0],'Recommend')
        self.assertEqual(intel.maturity('AUTO-FIX',25,.99,0)[0],'Verified Auto')
        self.assertEqual(intel.maturity('AUTO-STAGE',25,.99,0)[0],'Prepare')

    def test_month_gap_detection(self):
        self.assertEqual(intel.months_between('2026-01','2026-04'),['2026-01','2026-02','2026-03','2026-04'])
        self.assertEqual(intel.month_key('2026-04-22'),'2026-04')

    def test_templates_reference_registered_workflows_or_candidate(self):
        templates=json.loads((ROOT/'config/ava-workflow-templates.json').read_text())['templates']
        flows={w['id'] for w in json.loads((ROOT/'config/ava-executive-capabilities.json').read_text())['workflows']}
        self.assertGreaterEqual(len(templates),10)
        for t in templates:
            if t.get('workflow_id'):
                self.assertIn(t['workflow_id'],flows)
                self.assertEqual(t['state'],'production')
            else:
                self.assertEqual(t['state'],'candidate')

    def test_read_model_exposes_briefing_and_reviews(self):
        with tempfile.TemporaryDirectory() as td:
            db=Path(td)/'office.sqlite3'; store=OfficeManagerStore(db)
            with store.connect() as c:
                c.execute("INSERT INTO executive_briefings VALUES(?,?,?,?,?,?,?,?)",('daily:1','daily','a','b','Daily',json.dumps({'owner_actions_required':1}),1,'b'))
                c.execute("INSERT INTO executive_reviews VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",('r1','test','x','general','Needs review','detail','high','open',1,'review it','[]','a','b',None))
            model=AvaOfficeReadModel(db)
            self.assertEqual(model.latest_briefing()['summary']['owner_actions_required'],1)
            rows=model.reviews(owner_only=True)
            self.assertEqual(len(rows),1); self.assertTrue(rows[0]['owner_required'])

    def test_delegation_accepts_only_registered_workflow(self):
        with tempfile.TemporaryDirectory() as td:
            inbox=Path(td)/'inbox'; reg=Path(td)/'reg.json'
            reg.write_text(json.dumps({'workflows':[{'id':'safe','autonomous':True},{'id':'manual','autonomous':False}]}))
            with mock.patch.object(ava_dispatch_admin,'WORKFLOW_INBOX',inbox), mock.patch.object(ava_dispatch_admin,'REGISTRY',reg), mock.patch.object(ava_dispatch_admin.pwd,'getpwnam',return_value=mock.Mock(pw_uid=0,pw_gid=0)):
                result=ava_dispatch_admin.submit_workflow('safe','Do bounded work')
                self.assertEqual(result['status'],'queued')
                self.assertEqual(len(list(inbox.glob('*.json'))),1)
                with self.assertRaises(ValueError): ava_dispatch_admin.submit_workflow('manual','x')
                with self.assertRaises(ValueError): ava_dispatch_admin.submit_workflow('unknown','x')

if __name__=='__main__': unittest.main()
