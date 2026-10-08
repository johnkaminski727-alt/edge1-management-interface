from __future__ import annotations
import importlib.util, json, sqlite3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def load(name,path):
 spec=importlib.util.spec_from_file_location(name,ROOT/path); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

catalog=load('catalog_for_poll','tools/private_library/library_source_catalog.py')
poll=load('provider_poll_test','tools/private_library/provider_poll.py')

def test_provider_poll_reuses_existing_stable_item_id(tmp_path, monkeypatch):
 dbp=tmp_path/'catalog.sqlite3'; bridge=tmp_path/'bridge'; sid='google-drive-test'; ext='file-123'; stable='stable-existing-id'
 with sqlite3.connect(dbp) as db:
  db.row_factory=sqlite3.Row; db.executescript(catalog.SCHEMA)
  ts='2026-10-08T00:00:00+00:00'
  catalog.ensure_catalog_source(db,{'id':sid,'provider':'google-drive','name':'Test Drive','source_type':'google_drive_folder','locator':'gdrive-folder:x','runtime_access':'connector_required','copy_policy':'evidence'},ts)
  db.execute('''INSERT INTO library_items(id,source_id,external_id,item_type,title,copy_state,sync_state,first_seen_at,last_seen_at) VALUES(?,?,?,?,?,?,?,?,?)''',(stable,sid,ext,'document','Old','reference','current',ts,ts))
  db.execute("INSERT INTO library_item_domain_state(item_id,domain,state) VALUES(?,?,?)",(stable,'accounting','processed'))
  db.commit()
 p=bridge/sid; p.mkdir(parents=True); (p/'snapshot.json').write_text(json.dumps({'source_id':sid,'generated_at':'2026-10-08T01:00:00Z','complete':True,'items':[{'external_id':ext,'title':'New title','item_type':'document','copy_state':'reference'}]}))
 monkeypatch.setattr(poll,'BRIDGE',bridge)
 with sqlite3.connect(dbp) as db:
  db.row_factory=sqlite3.Row; db.execute('PRAGMA foreign_keys=ON'); source=db.execute('select * from library_sources where id=?',(sid,)).fetchone(); out=poll.poll_one(db,source); db.commit()
  assert out['status']=='succeeded'
  row=db.execute('select id,title from library_items where source_id=? and external_id=?',(sid,ext)).fetchone()
  assert row['id']==stable and row['title']=='New title'
  assert db.execute('pragma foreign_key_check').fetchall()==[]

def test_missing_bridge_is_deferred(tmp_path, monkeypatch):
 dbp=tmp_path/'catalog.sqlite3'; bridge=tmp_path/'bridge'; sid='dropbox-test'
 with sqlite3.connect(dbp) as db:
  db.row_factory=sqlite3.Row; db.executescript(catalog.SCHEMA); catalog.ensure_catalog_source(db,{'id':sid,'provider':'dropbox','name':'Test','source_type':'dropbox_folder','locator':'/x','runtime_access':'connector_required','copy_policy':'reference'},'2026-10-08T00:00:00Z'); db.commit()
 monkeypatch.setattr(poll,'BRIDGE',bridge)
 with sqlite3.connect(dbp) as db:
  db.row_factory=sqlite3.Row; source=db.execute('select * from library_sources where id=?',(sid,)).fetchone(); out=poll.poll_one(db,source)
  assert out['status']=='deferred' and out['deferred']==1


def test_changed_provider_run_submits_ava_workflow_once(tmp_path):
 inbox=tmp_path/'workflow-inbox'
 out=[{'source_id':'dropbox-test','status':'succeeded','new_items':2,'changed_items':1,'detail':{'snapshot_generated_at':'2026-10-08T02:00:00Z'}}]
 first=poll.submit_workflow_if_changed(out,'2026-10-08T02:01:00Z',inbox)
 assert first is not None and first.is_file()
 payload=json.loads(first.read_text())
 assert payload['workflow_id']=='provider-evidence-processing'
 assert payload['detail']['changed_items']==3
 first.rename(first.with_suffix('.processed'))
 second=poll.submit_workflow_if_changed(out,'2026-10-08T02:02:00Z',inbox)
 assert second is not None
 assert not second.is_file()
 assert second.with_suffix('.processed').is_file()

def test_unchanged_provider_run_does_not_submit_workflow(tmp_path):
 inbox=tmp_path/'workflow-inbox'
 out=[{'source_id':'dropbox-test','status':'succeeded','new_items':0,'changed_items':0,'detail':{}}]
 assert poll.submit_workflow_if_changed(out,'2026-10-08T02:01:00Z',inbox) is None
 assert not inbox.exists()
