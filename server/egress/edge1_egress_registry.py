from __future__ import annotations
import json, sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_DB=Path('/var/lib/edge1-egress/egress.sqlite3')
DEFAULT_TRIGGER=Path('/var/lib/edge1-egress/reconcile.trigger')
ALLOWED_GATEWAYS={'direct','us','ca','mx'}
SCHEMA='wwcx.edge1-egress.v1'

DDL='''
CREATE TABLE IF NOT EXISTS services(
 id TEXT PRIMARY KEY,
 label TEXT NOT NULL,
 gateway TEXT NOT NULL CHECK(gateway IN ('direct','us','ca','mx')),
 enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0,1)),
 fail_mode TEXT NOT NULL DEFAULT 'closed' CHECK(fail_mode IN ('closed','direct')),
 domains_json TEXT NOT NULL,
 description TEXT NOT NULL DEFAULT '',
 updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 service_id TEXT NOT NULL,
 actor TEXT NOT NULL,
 request_id TEXT NOT NULL,
 changed_fields_json TEXT NOT NULL,
 before_json TEXT NOT NULL,
 after_json TEXT NOT NULL,
 created_at TEXT NOT NULL
);
'''

def now()->str:
 return datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')

def connect(path:Path=DEFAULT_DB, read_only:bool=False):
 if read_only:
  c=sqlite3.connect(f'file:{path}?mode=ro',uri=True)
 else:c=sqlite3.connect(path)
 c.row_factory=sqlite3.Row
 return c

def init_db(path:Path=DEFAULT_DB):
 path.parent.mkdir(parents=True,exist_ok=True)
 with connect(path) as c:
  c.executescript(DDL)
  row=c.execute("select 1 from services where id='disney-plus'").fetchone()
  if not row:
   domains=['disneyplus.com','disney-plus.net','bamgrid.com','dssott.com']
   c.execute('insert into services(id,label,gateway,enabled,fail_mode,domains_json,description,updated_at) values(?,?,?,?,?,?,?,?)',
    ('disney-plus','Disney+','us',1,'closed',json.dumps(domains,separators=(',',':')),
     'Route Disney+ service traffic through the United States egress pool.',now()))
  c.commit()

def _item(r):
 d=dict(r); d['enabled']=bool(d['enabled']); d['domains']=json.loads(d.pop('domains_json')); return d

def list_services(path:Path=DEFAULT_DB)->list[dict[str,Any]]:
 with connect(path,True) as c:return [_item(r) for r in c.execute('select * from services order by label,id')]

def list_audit(path:Path=DEFAULT_DB,limit:int=40):
 limit=max(1,min(int(limit),200))
 with connect(path,True) as c: rows=c.execute('select id,service_id,actor,request_id,changed_fields_json,created_at from audit order by id desc limit ?',(limit,)).fetchall()
 out=[]
 for r in rows:
  d=dict(r);d['changed_fields']=json.loads(d.pop('changed_fields_json'));out.append(d)
 return out

def update_service(service_id:str,patch:dict[str,Any],actor='authenticated_admin',request_id='browser-request',path:Path=DEFAULT_DB):
 allowed={'gateway','enabled','fail_mode'}
 if set(patch)-allowed: raise ValueError('unsupported fields')
 if not patch: raise ValueError('empty patch')
 with connect(path) as c:
  c.executescript(DDL);c.execute('begin immediate')
  row=c.execute('select * from services where id=?',(service_id,)).fetchone()
  if row is None: c.rollback();raise KeyError(service_id)
  before=dict(row); clean={}
  if 'gateway' in patch:
   if patch['gateway'] not in ALLOWED_GATEWAYS: raise ValueError('invalid gateway')
   clean['gateway']=patch['gateway']
  if 'enabled' in patch:
   if not isinstance(patch['enabled'],bool):raise ValueError('enabled must be boolean')
   clean['enabled']=int(patch['enabled'])
  if 'fail_mode' in patch:
   if patch['fail_mode'] not in {'closed','direct'}:raise ValueError('invalid fail mode')
   clean['fail_mode']=patch['fail_mode']
  cols=list(clean);vals=[clean[x] for x in cols]
  c.execute('update services set '+','.join(f'{x}=?' for x in cols)+',updated_at=? where id=?',vals+[now(),service_id])
  after=dict(c.execute('select * from services where id=?',(service_id,)).fetchone())
  changed=[x for x in cols if before.get(x)!=after.get(x)]
  if changed:c.execute('insert into audit(service_id,actor,request_id,changed_fields_json,before_json,after_json,created_at) values(?,?,?,?,?,?,?)',
   (service_id,actor,request_id,json.dumps(changed,separators=(',',':')),json.dumps(before,separators=(',',':')),json.dumps(after,separators=(',',':')),now()))
  c.commit()
 DEFAULT_TRIGGER.touch()
 return _item(after),changed
