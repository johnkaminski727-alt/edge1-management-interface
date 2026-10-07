#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, re, sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

SCHEMA='''
CREATE TABLE IF NOT EXISTS maintenance_runs(
 id INTEGER PRIMARY KEY AUTOINCREMENT, started_at TEXT NOT NULL, finished_at TEXT,
 source_sha256 TEXT, status TEXT NOT NULL, summary_json TEXT
);
CREATE TABLE IF NOT EXISTS maintenance_findings(
 id INTEGER PRIMARY KEY AUTOINCREMENT, fingerprint TEXT NOT NULL UNIQUE,
 finding_type TEXT NOT NULL, severity TEXT NOT NULL, entity_id INTEGER,
 contact_point_id INTEGER, title TEXT NOT NULL, detail TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'open', first_seen_at TEXT NOT NULL,
 last_seen_at TEXT NOT NULL, occurrences INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS enrichment_queue(
 id INTEGER PRIMARY KEY AUTOINCREMENT, fingerprint TEXT NOT NULL UNIQUE,
 entity_id INTEGER NOT NULL, task_type TEXT NOT NULL, rationale TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_findings_status ON maintenance_findings(status, finding_type);
CREATE INDEX IF NOT EXISTS idx_enrichment_status ON enrichment_queue(status, task_type);
'''

def utcnow(): return datetime.now(timezone.utc).isoformat(timespec='seconds')
def norm_name(s): return re.sub(r'[^a-z0-9]+','', (s or '').casefold())
def fp(*parts): return hashlib.sha256('|'.join('' if p is None else str(p) for p in parts).encode()).hexdigest()

def open_source(path):
 c=sqlite3.connect(f'file:{path}?mode=ro', uri=True); c.row_factory=sqlite3.Row; c.execute('PRAGMA foreign_keys=ON'); return c

def open_state(path):
 path.parent.mkdir(parents=True, exist_ok=True); c=sqlite3.connect(path); c.row_factory=sqlite3.Row; c.executescript(SCHEMA); return c

def source_sha(path):
 h=hashlib.sha256();
 with open(path,'rb') as f:
  for b in iter(lambda:f.read(1024*1024), b''): h.update(b)
 return h.hexdigest()

def finding(dst, kind, sev, title, detail, entity=None, point=None):
 now=utcnow(); key=fp(kind, entity, point, title, detail)
 dst.execute('''INSERT INTO maintenance_findings(fingerprint,finding_type,severity,entity_id,contact_point_id,title,detail,first_seen_at,last_seen_at)
 VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(fingerprint) DO UPDATE SET last_seen_at=excluded.last_seen_at, occurrences=maintenance_findings.occurrences+1, status=CASE WHEN maintenance_findings.status='resolved' THEN 'open' ELSE maintenance_findings.status END''',
 (key,kind,sev,entity,point,title,detail,now,now))

def enrich(dst, entity, task, rationale):
 now=utcnow(); key=fp(entity,task)
 dst.execute('''INSERT INTO enrichment_queue(fingerprint,entity_id,task_type,rationale,created_at,updated_at)
 VALUES(?,?,?,?,?,?) ON CONFLICT(fingerprint) DO UPDATE SET rationale=excluded.rationale, updated_at=excluded.updated_at''',(key,entity,task,rationale,now,now))

def run(src, dst):
 # duplicates by canonical normalized name
 rows=src.execute("SELECT id,entity_type,canonical_name FROM contact_entities WHERE lifecycle_status='active'").fetchall(); groups={}
 for r in rows: groups.setdefault((r['entity_type'],norm_name(r['canonical_name'])),[]).append(r)
 for (typ,key), rs in groups.items():
  if key and len(rs)>1:
   ids=[r['id'] for r in rs]; finding(dst,'duplicate_entity','high','Possible duplicate contacts',f"{typ} records share normalized name {rs[0]['canonical_name']!r}; entity_ids={ids}")
 # contact point shared across multiple active entities
 for r in src.execute('''SELECT cp.id,cp.point_type,cp.normalized_value,COUNT(DISTINCT ca.entity_id) n,GROUP_CONCAT(DISTINCT ca.entity_id) ids
 FROM contact_points cp JOIN contact_assertions ca ON ca.contact_point_id=cp.id JOIN contact_entities e ON e.id=ca.entity_id
 WHERE cp.lifecycle_status='active' AND e.lifecycle_status='active' GROUP BY cp.id HAVING COUNT(DISTINCT ca.entity_id)>1'''):
  finding(dst,'shared_contact_point','medium','Contact point belongs to multiple contacts',f"{r['point_type']} {r['normalized_value']} is asserted for entity_ids={r['ids']}",point=r['id'])
 # unassigned points
 for r in src.execute('''SELECT cp.id,cp.point_type,cp.normalized_value FROM contact_points cp WHERE cp.lifecycle_status='active' AND NOT EXISTS(SELECT 1 FROM contact_assertions ca WHERE ca.contact_point_id=cp.id)'''):
  finding(dst,'unassigned_contact_point','low','Unassigned contact point',f"{r['point_type']} {r['normalized_value']} has no canonical entity",point=r['id'])
 # incomplete entities -> enrichment queue
 for e in rows:
  types={x[0] for x in src.execute('''SELECT DISTINCT cp.point_type FROM contact_assertions ca JOIN contact_points cp ON cp.id=ca.contact_point_id WHERE ca.entity_id=? AND cp.lifecycle_status='active' ''',(e['id'],))}
  if 'phone' not in types: enrich(dst,e['id'],'find_phone','No active phone is recorded.')
  if 'email' not in types: enrich(dst,e['id'],'find_email','No active email is recorded.')
  if e['entity_type']=='organization' and not ({'domain','website'} & types): enrich(dst,e['id'],'find_web_presence','No domain or website is recorded.')
  if 'postal_address' not in types: enrich(dst,e['id'],'find_address','No postal address is recorded.')
 # lightweight syntax validation
 for r in src.execute("SELECT id,point_type,normalized_value FROM contact_points WHERE lifecycle_status='active'"):
  v=(r['normalized_value'] or '').strip(); bad=False
  if r['point_type']=='email': bad=not bool(re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+',v))
  elif r['point_type']=='domain': bad=not bool(re.fullmatch(r'(?=.{1,253}$)([A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}',v))
  elif r['point_type'] in ('phone','fax'): bad=len(re.sub(r'\D','',v))<7
  if bad: finding(dst,'validation_issue','medium','Contact point needs validation',f"{r['point_type']} value {v!r} failed basic syntax validation",point=r['id'])
 return {
  'entities':len(rows),
  'open_findings':dst.execute("SELECT COUNT(*) FROM maintenance_findings WHERE status='open'").fetchone()[0],
  'pending_enrichment':dst.execute("SELECT COUNT(*) FROM enrichment_queue WHERE status='pending'").fetchone()[0],
 }

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--source',default='/var/lib/edge1-phone-intelligence/phone-intelligence.sqlite'); ap.add_argument('--state',default='/var/lib/edge1-contacts-maintenance/maintenance.sqlite'); ap.add_argument('--json',action='store_true'); a=ap.parse_args()
 sp=Path(a.source); dp=Path(a.state)
 if not sp.is_file(): raise SystemExit('source database missing')
 with closing(open_source(sp)) as src, closing(open_state(dp)) as dst:
  started=utcnow(); sha=source_sha(sp); cur=dst.execute("INSERT INTO maintenance_runs(started_at,source_sha256,status) VALUES(?,?,?)",(started,sha,'running')); rid=cur.lastrowid
  try:
   summary=run(src,dst); summary['run_id']=rid; summary['source_sha256']=sha
   dst.execute("UPDATE maintenance_runs SET finished_at=?,status='ok',summary_json=? WHERE id=?",(utcnow(),json.dumps(summary,sort_keys=True),rid)); dst.commit()
  except Exception as exc:
   dst.execute("UPDATE maintenance_runs SET finished_at=?,status='failed',summary_json=? WHERE id=?",(utcnow(),json.dumps({'error':str(exc)}),rid)); dst.commit(); raise
 print(json.dumps(summary,sort_keys=True) if a.json else summary)
if __name__=='__main__': main()
