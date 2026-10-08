from __future__ import annotations
import importlib.util, sqlite3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('catalog_reconcile',ROOT/'tools/private_library/library_source_catalog.py'); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
def test_registry_refresh_preserves_provider_sync_status(tmp_path):
 p=tmp_path/'c.sqlite3'
 with sqlite3.connect(p) as db:
  db.row_factory=sqlite3.Row; db.executescript(m.SCHEMA)
  s={'id':'g','provider':'google-drive','name':'Drive','source_type':'folder','locator':'x','runtime_access':'connector_required','copy_policy':'evidence'}
  m.ensure_catalog_source(db,s,'t1'); db.execute("update library_sources set last_status='succeeded',last_sync_at='t2' where id='g'"); m.ensure_catalog_source(db,s,'t3')
  r=db.execute("select last_status,last_sync_at from library_sources where id='g'").fetchone(); assert tuple(r)==('succeeded','t2')
def test_new_catalog_item_id_is_source_scoped(tmp_path):
 p=tmp_path/'c.sqlite3'
 with sqlite3.connect(p) as db:
  db.row_factory=sqlite3.Row; db.executescript(m.SCHEMA)
  for sid in ('a','b'): m.ensure_catalog_source(db,{'id':sid,'provider':'google-drive','name':sid,'source_type':'folder','locator':sid,'runtime_access':'connector_required','copy_policy':'reference'},'t')
  a=m.upsert_item(db,'a','google-drive','same','A','t'); b=m.upsert_item(db,'b','google-drive','same','B','t'); assert a!=b
