#!/usr/bin/env python3
from __future__ import annotations
import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from server.ava_office_manager import OfficeManagerStore
from tools.automation import ava_workflow_dispatcher as d
from tools.private_library import provider_poll as provider_poll

class AvaWorkflowDispatcherTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name); self.db=self.root/'office.sqlite3'; self.store=OfficeManagerStore(self.db)
  self.store.upsert_team_member(member_id='test-bot',display_name='Test Bot',department='Automation & Operations',role='Test',action_level='AUTO-FIX',authority_ceiling='routine',capabilities=['test.run'],health_state='healthy')
  self.registry=self.root/'registry.json'; self.registry.write_text(json.dumps({'contract':'wwcx.ava-executive-capabilities.v1','default_timeout_seconds':5,'capabilities':[{'id':'test.run','team_member':'test-bot','authority':'routine','autonomous':True,'transport':'http_json','endpoint':'http://127.0.0.1:9999/test','method':'POST','headers':{},'body':{},'success_statuses':[200]}],'workflows':[{'id':'test-flow','name':'Test Flow','autonomous':True,'trigger':'test','description':'test workflow','steps':[{'id':'one','capability':'test.run','depends_on':[]},{'id':'two','capability':'test.run','depends_on':['one']}]}]}))
 def tearDown(self): self.tmp.cleanup()
 def test_registered_workflow_runs_dependencies_to_completion(self):
  reg=d.load_registry(self.registry); run_id,new=d.create_run(self.store,reg,{'workflow_id':'test-flow','trigger_ref':'event:1','trigger_type':'test'})
  self.assertTrue(new)
  with patch.object(d,'invoke',return_value={'ok':True,'http_status':200,'response':{'status':'succeeded'}}): stats=d.dispatch_ready(self.store,reg)
  self.assertEqual(stats['steps_completed'],2)
  with self.store.connect() as c:
   self.assertEqual(c.execute('select state from executive_workflow_runs where id=?',(run_id,)).fetchone()[0],'completed')
   self.assertEqual(c.execute("select count(*) from executive_workflow_steps where run_id=? and state='completed'",(run_id,)).fetchone()[0],2)
 def test_trigger_is_idempotent(self):
  reg=d.load_registry(self.registry); a=d.create_run(self.store,reg,{'workflow_id':'test-flow','trigger_ref':'same'}); b=d.create_run(self.store,reg,{'workflow_id':'test-flow','trigger_ref':'same'})
  self.assertEqual(a[0],b[0]); self.assertFalse(b[1])
 def test_authority_ceiling_blocks_capability(self):
  reg=d.load_registry(self.registry)
  with self.store.connect() as c:c.execute("update executive_team_members set authority_ceiling='observe' where member_id='test-bot'")
  run_id,_=d.create_run(self.store,reg,{'workflow_id':'test-flow','trigger_ref':'blocked'})
  stats=d.dispatch_ready(self.store,reg)
  self.assertGreaterEqual(stats['steps_blocked'],1)
  with self.store.connect() as c:self.assertEqual(c.execute('select state from executive_workflow_runs where id=?',(run_id,)).fetchone()[0],'failed')
 def test_registry_rejects_non_loopback(self):
  x=json.loads(self.registry.read_text()); x['capabilities'][0]['endpoint']='https://example.com/action'; self.registry.write_text(json.dumps(x))
  with self.assertRaises(d.DispatchError): d.load_registry(self.registry)

 def test_provider_delta_submits_idempotent_workflow_request(self):
  inbox=self.root/'provider-workflow-inbox'
  out=[{'source_id':'provider-x','status':'succeeded','new_items':1,'changed_items':2,'detail':{'snapshot_generated_at':'2026-10-08T02:00:00Z'}}]
  first=provider_poll.submit_workflow_if_changed(out,'2026-10-08T02:01:00Z',inbox)
  self.assertIsNotNone(first); self.assertTrue(first.is_file())
  payload=json.loads(first.read_text()); self.assertEqual(payload['workflow_id'],'provider-evidence-processing'); self.assertEqual(payload['detail']['changed_items'],3)
  first.rename(first.with_suffix('.processed'))
  second=provider_poll.submit_workflow_if_changed(out,'2026-10-08T02:02:00Z',inbox)
  self.assertFalse(second.is_file()); self.assertTrue(second.with_suffix('.processed').is_file())

 def test_team_attention_reuses_existing_work_item_and_waits_for_checkin(self):
  reg=d.load_registry(self.registry)
  work=self.store.create_work_item(title='Attention',desired_outcome='Recover bot',source_channel='ava-executive',source_ref='ava-attention:test-bot',owner='ava')
  run_id,_=d.create_run(self.store,reg,{'workflow_id':'test-flow','trigger_ref':'attention:1','trigger_type':'team-attention','work_item_id':work['id']})
  with patch.object(d,'invoke',return_value={'ok':True,'http_status':200,'response':{'status':'succeeded'}}): d.dispatch_ready(self.store,reg)
  with self.store.connect() as c:
   self.assertEqual(c.execute('select work_item_id from executive_workflow_runs where id=?',(run_id,)).fetchone()[0],work['id'])
  self.assertEqual(self.store.get_work_item(work['id'])['state'],'waiting_external')

if __name__=='__main__': unittest.main()

