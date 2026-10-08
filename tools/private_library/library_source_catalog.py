#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, sqlite3, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path('/opt/edge1-management-interface')
CATALOG=Path('/var/lib/bigbird-ai-library/catalog/source-catalog.sqlite3')
LIB=Path('/var/lib/bigbird-ai-library/library.sqlite3')
CONTACTS=Path('/var/lib/edge1-phone-intelligence/phone-intelligence.sqlite')
REGISTRY=ROOT/'config/contacts/contact-source-registry.json'
SOURCE_REGISTRY=ROOT/'config/private-library/source-catalog.json'
STATUS=Path('/var/www/edge1-status/library-source-catalog/status.json')
sys.path.insert(0,str(ROOT))
from tools.automation.automation_common import upsert_library_document

SCHEMA='''
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS library_sources(
 id TEXT PRIMARY KEY,
 provider TEXT NOT NULL,
 name TEXT NOT NULL,
 source_type TEXT NOT NULL,
 locator TEXT NOT NULL,
 runtime_access TEXT NOT NULL,
 enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN(0,1)),
 authority TEXT,
 default_action TEXT,
 copy_policy TEXT NOT NULL DEFAULT 'reference' CHECK(copy_policy IN('reference','cache','evidence')),
 classification TEXT NOT NULL DEFAULT 'internal',
 sensitivity TEXT NOT NULL DEFAULT 'normal',
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 last_sync_at TEXT,
 last_status TEXT NOT NULL DEFAULT 'new',
 last_error TEXT
);
CREATE TABLE IF NOT EXISTS library_items(
 id TEXT PRIMARY KEY,
 source_id TEXT NOT NULL REFERENCES library_sources(id) ON DELETE CASCADE,
 external_id TEXT,
 parent_external_id TEXT,
 item_type TEXT NOT NULL DEFAULT 'document',
 title TEXT NOT NULL,
 original_name TEXT,
 source_url TEXT,
 source_path TEXT,
 mime_type TEXT,
 size_bytes INTEGER,
 provider_created_at TEXT,
 provider_modified_at TEXT,
 revision_id TEXT,
 content_sha256 TEXT,
 local_path TEXT,
 evidence_source_document_id INTEGER,
 library_document_id TEXT,
 copy_state TEXT NOT NULL DEFAULT 'reference' CHECK(copy_state IN('reference','cached','preserved','missing','unavailable')),
 sync_state TEXT NOT NULL DEFAULT 'current' CHECK(sync_state IN('current','new','changed','deleted_remote','deferred','error')),
 first_seen_at TEXT NOT NULL,
 last_seen_at TEXT NOT NULL,
 indexed_at TEXT,
 UNIQUE(source_id,external_id)
);
CREATE INDEX IF NOT EXISTS idx_library_items_source ON library_items(source_id,sync_state);
CREATE INDEX IF NOT EXISTS idx_library_items_sha ON library_items(content_sha256);
CREATE INDEX IF NOT EXISTS idx_library_items_evidence ON library_items(evidence_source_document_id);
CREATE TABLE IF NOT EXISTS library_item_metadata(
 item_id TEXT NOT NULL REFERENCES library_items(id) ON DELETE CASCADE,
 key TEXT NOT NULL,
 value_json TEXT NOT NULL,
 provenance TEXT NOT NULL DEFAULT 'source',
 updated_at TEXT NOT NULL,
 PRIMARY KEY(item_id,key)
);
CREATE TABLE IF NOT EXISTS library_item_domain_state(
 item_id TEXT NOT NULL REFERENCES library_items(id) ON DELETE CASCADE,
 domain TEXT NOT NULL,
 state TEXT NOT NULL DEFAULT 'pending',
 processor_version TEXT,
 last_processed_at TEXT,
 detail_json TEXT,
 PRIMARY KEY(item_id,domain)
);
CREATE TABLE IF NOT EXISTS accounting_document_facts(
 item_id TEXT PRIMARY KEY REFERENCES library_items(id) ON DELETE CASCADE,
 vendor_name TEXT,
 document_kind TEXT,
 issue_date TEXT,
 period_start TEXT,
 period_end TEXT,
 account_reference TEXT,
 invoice_number TEXT,
 currency TEXT,
 subtotal TEXT,
 tax_total TEXT,
 total_amount TEXT,
 balance_due TEXT,
 due_date TEXT,
 payment_status TEXT,
 duplicate_key TEXT,
 extraction_confidence TEXT,
 review_status TEXT NOT NULL DEFAULT 'pending',
 source_sha256 TEXT,
 updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_accounting_doc_review ON accounting_document_facts(review_status,document_kind);
CREATE TABLE IF NOT EXISTS accounting_line_items(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 item_id TEXT NOT NULL REFERENCES library_items(id) ON DELETE CASCADE,
 line_index INTEGER NOT NULL,
 description TEXT NOT NULL,
 quantity TEXT,
 unit_amount TEXT,
 line_amount TEXT,
 tax_code TEXT,
 service_period_start TEXT,
 service_period_end TEXT,
 metadata_json TEXT,
 UNIQUE(item_id,line_index)
);
CREATE TABLE IF NOT EXISTS accounting_reconciliation_links(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 item_id TEXT NOT NULL REFERENCES library_items(id) ON DELETE CASCADE,
 external_system TEXT NOT NULL,
 external_record_id TEXT NOT NULL,
 relationship TEXT NOT NULL,
 confidence TEXT NOT NULL DEFAULT 'unverified',
 review_status TEXT NOT NULL DEFAULT 'pending',
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL,
 UNIQUE(item_id,external_system,external_record_id,relationship)
);
CREATE TABLE IF NOT EXISTS library_sync_runs(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 source_id TEXT REFERENCES library_sources(id) ON DELETE SET NULL,
 started_at TEXT NOT NULL,
 finished_at TEXT,
 status TEXT NOT NULL,
 scanned INTEGER NOT NULL DEFAULT 0,
 new_items INTEGER NOT NULL DEFAULT 0,
 changed_items INTEGER NOT NULL DEFAULT 0,
 preserved INTEGER NOT NULL DEFAULT 0,
 indexed INTEGER NOT NULL DEFAULT 0,
 deferred INTEGER NOT NULL DEFAULT 0,
 errors INTEGER NOT NULL DEFAULT 0,
 detail_json TEXT
);
'''

def now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
def sid(provider, external): return hashlib.sha256(f'{provider}:{external}'.encode()).hexdigest()
def provider_for(kind):
 return {'airtable':'airtable','chatgpt_library_register':'chatgpt-library','private_library':'edge1-private-library','edge1_register':'edge1','message_source':'mail','google_drive_folder':'google-drive'}.get(kind,kind or 'unknown')
def policy_for(source):
 rules=set(source.get('rules') or [])
 if 'preserve_original_bytes' in rules: return 'evidence'
 if source.get('kind') in {'edge1_register'}: return 'evidence'
 return 'reference'

def ensure_source(db,s,ts):
 p=provider_for(s.get('kind'))
 db.execute('''INSERT INTO library_sources(id,provider,name,source_type,locator,runtime_access,enabled,authority,default_action,copy_policy,classification,sensitivity,created_at,updated_at,last_status)
 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
 ON CONFLICT(id) DO UPDATE SET provider=excluded.provider,name=excluded.name,source_type=excluded.source_type,locator=excluded.locator,runtime_access=excluded.runtime_access,enabled=excluded.enabled,authority=excluded.authority,default_action=excluded.default_action,copy_policy=excluded.copy_policy,updated_at=excluded.updated_at''',
 (s['id'],p,s['name'],s.get('kind','unknown'),s.get('locator',''),s.get('runtime_access','unknown'),1 if s.get('ingestion') not in {'disabled'} else 0,s.get('authority'),s.get('default_action'),policy_for(s),'internal','restricted' if 'restricted' in str(s.get('authority','')) else 'normal',ts,ts,'deferred' if s.get('runtime_access')=='connector_required' else 'available'))

def ensure_catalog_source(db,s,ts):
 db.execute('''INSERT INTO library_sources(id,provider,name,source_type,locator,runtime_access,enabled,authority,default_action,copy_policy,classification,sensitivity,created_at,updated_at,last_status)
 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
 ON CONFLICT(id) DO UPDATE SET provider=excluded.provider,name=excluded.name,source_type=excluded.source_type,locator=excluded.locator,runtime_access=excluded.runtime_access,enabled=excluded.enabled,copy_policy=excluded.copy_policy,classification=excluded.classification,sensitivity=excluded.sensitivity,updated_at=excluded.updated_at''',
 (s['id'],s['provider'],s['name'],s.get('source_type','unknown'),s.get('locator',''),s.get('runtime_access','unknown'),1 if s.get('enabled',True) else 0,s.get('authority'),s.get('default_action'),s.get('copy_policy','reference'),s.get('classification','internal'),s.get('sensitivity','normal'),ts,ts,'deferred' if s.get('runtime_access')=='connector_required' else 'available'))


def bootstrap_source_registry(db,ts):
 if not SOURCE_REGISTRY.is_file(): return 0
 data=json.loads(SOURCE_REGISTRY.read_text())
 for s in data.get('sources',[]): ensure_catalog_source(db,s,ts)
 return len(data.get('sources',[]))


def upsert_item(db, source_id, provider, external_id, title, ts, **kw):
 existing=db.execute('SELECT id FROM library_items WHERE source_id=? AND external_id=?',(source_id,external_id)).fetchone()
 iid=existing[0] if existing else sid(source_id,external_id)
 db.execute('''INSERT INTO library_items(id,source_id,external_id,parent_external_id,item_type,title,original_name,source_url,source_path,mime_type,size_bytes,provider_created_at,provider_modified_at,revision_id,content_sha256,local_path,evidence_source_document_id,library_document_id,copy_state,sync_state,first_seen_at,last_seen_at,indexed_at)
 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
 ON CONFLICT(id) DO UPDATE SET title=excluded.title,original_name=COALESCE(excluded.original_name,library_items.original_name),source_url=COALESCE(excluded.source_url,library_items.source_url),source_path=COALESCE(excluded.source_path,library_items.source_path),mime_type=COALESCE(excluded.mime_type,library_items.mime_type),size_bytes=COALESCE(excluded.size_bytes,library_items.size_bytes),provider_modified_at=COALESCE(excluded.provider_modified_at,library_items.provider_modified_at),revision_id=COALESCE(excluded.revision_id,library_items.revision_id),content_sha256=COALESCE(excluded.content_sha256,library_items.content_sha256),local_path=COALESCE(excluded.local_path,library_items.local_path),evidence_source_document_id=COALESCE(excluded.evidence_source_document_id,library_items.evidence_source_document_id),library_document_id=COALESCE(excluded.library_document_id,library_items.library_document_id),copy_state=excluded.copy_state,sync_state=excluded.sync_state,last_seen_at=excluded.last_seen_at''',
 (iid,source_id,external_id,kw.get('parent_external_id'),kw.get('item_type','document'),title,kw.get('original_name'),kw.get('source_url'),kw.get('source_path'),kw.get('mime_type'),kw.get('size_bytes'),kw.get('provider_created_at'),kw.get('provider_modified_at'),kw.get('revision_id'),kw.get('content_sha256'),kw.get('local_path'),kw.get('evidence_source_document_id'),kw.get('library_document_id'),kw.get('copy_state','reference'),kw.get('sync_state','current'),ts,ts,kw.get('indexed_at')))
 for domain in ('contacts','accounting','filing'):
  db.execute('INSERT OR IGNORE INTO library_item_domain_state(item_id,domain,state) VALUES(?,?,?)',(iid,domain,'pending'))
 return iid

def bootstrap_registry(db,ts):
 if not REGISTRY.is_file(): return 0
 data=json.loads(REGISTRY.read_text()); n=0
 for s in data.get('sources',[]): ensure_source(db,s,ts); n+=1
 return n

def evidence_source_id(db, row):
 ref=str(row['source_reference'] or '')
 name=str(row['source_name'] or '')
 candidates=[dict(r) for r in db.execute('SELECT id,provider,locator,name FROM library_sources')]
 if ref.startswith('gdrive:'):
  gd=[r for r in candidates if r['provider']=='google-drive']
  if len(gd)==1: return gd[0]['id']
 if ref.startswith('airtable:'):
  for r in candidates:
   if r['provider']=='airtable' and str(r['locator']) and ref.startswith(str(r['locator'])): return r['id']
  if 'Organization' in name and any(r['id']=='airtable-operations-organizations' for r in candidates): return 'airtable-operations-organizations'
  if ('People' in name or 'Contact' in name) and any(r['id']=='airtable-operations-people' for r in candidates): return 'airtable-operations-people'
 if ref.startswith('library:'):
  for r in candidates:
   if r['provider']=='chatgpt-library' and str(r['locator']).split('#')[0] == ref.split('#')[0]: return r['id']
 if ref.endswith('mail-identities.json'): return 'messaging-identity-registry'
 if ref.endswith('mail-provider-inventory.json'): return 'mail-provider-inventory'
 return 'edge1-evidence-register'

def bootstrap_evidence(db,ts):
 if not CONTACTS.is_file(): return 0
 # Synthetic source for evidence records not mapped elsewhere.
 ensure_source(db,{'id':'edge1-evidence-register','name':'Edge1 Evidence Register','kind':'edge1_register','locator':'/var/lib/edge1-evidence-intake','runtime_access':'local','ingestion':'enabled','authority':'evidence_provenance','default_action':'AUTO_STAGE','rules':['preserve_original_bytes']},ts)
 with sqlite3.connect(f'file:{CONTACTS}?mode=ro',uri=True) as c:
  c.row_factory=sqlite3.Row
  rows=c.execute('SELECT id,document_type,source_name,source_reference,sha256,verification_status,notes,created_at FROM source_documents ORDER BY id').fetchall()
 n=0
 for r in rows:
  source_id=evidence_source_id(db,r)
  provider=db.execute('SELECT provider FROM library_sources WHERE id=?',(source_id,)).fetchone()[0]
  ref=str(r['source_reference'] or '')
  ext=ref.split(':',1)[1] if ref.startswith('gdrive:') else f"source_document:{r['id']}"
  # If evidence was catalogued before the provider bridge exposed its real external ID,
  # preserve the established item ID and downstream links, merge the transient provider row,
  # then promote the evidence row to the real provider identifier.
  oldrow=db.execute("SELECT id,external_id FROM library_items WHERE source_id=? AND evidence_source_document_id=? ORDER BY CASE WHEN external_id LIKE 'source_document:%' THEN 0 ELSE 1 END,id LIMIT 1",(source_id,r['id'])).fetchone()
  target=db.execute('SELECT id FROM library_items WHERE source_id=? AND external_id=?',(source_id,ext)).fetchone()
  if oldrow and target and oldrow['id']!=target['id']:
   # Keep the evidence-backed item because it may already own accounting/domain/library links.
   db.execute('DELETE FROM library_items WHERE id=?',(target['id'],))
   target=None
  if oldrow and oldrow['external_id']!=ext:
   db.execute('UPDATE library_items SET external_id=? WHERE id=?',(ext,oldrow['id']))
  local=None
  if r['sha256']:
   root=Path('/var/lib/edge1-evidence-intake/objects')/r['sha256'][:2]/r['sha256']
   if root.is_dir():
    files=[p for p in root.iterdir() if p.is_file()]
    if files: local=str(files[0])
  copy_state='preserved' if local else ('reference' if not r['sha256'] else 'missing')
  iid=upsert_item(db,source_id,provider,ext,r['source_name'],ts,item_type=r['document_type'],source_path=r['source_reference'],content_sha256=r['sha256'],local_path=local,evidence_source_document_id=r['id'],copy_state=copy_state)
  db.execute('INSERT OR REPLACE INTO library_item_metadata(item_id,key,value_json,provenance,updated_at) VALUES(?,?,?,?,?)',(iid,'verification_status',json.dumps(r['verification_status']),'evidence-register',ts))
  n+=1
 return n

def link_library_documents(db,ts):
 if not LIB.is_file(): return 0
 ensure_source(db,{'id':'edge1-private-library-runtime','name':'Edge1 Private Library Runtime','kind':'private_library','locator':str(LIB),'runtime_access':'local','ingestion':'enabled','authority':'search_index','default_action':'AUTO_STAGE'},ts)
 with sqlite3.connect(f'file:{LIB}?mode=ro',uri=True) as c:
  c.row_factory=sqlite3.Row; rows=c.execute("SELECT id,title,source_path,classification,updated_at FROM documents WHERE source_path NOT LIKE 'external/%'").fetchall()
 for r in rows:
  upsert_item(db,'edge1-private-library-runtime','edge1-private-library',r['id'],r['title'],ts,item_type='indexed_document',source_path=r['source_path'],library_document_id=r['id'],copy_state='reference',indexed_at=r['updated_at'])
 return len(rows)

def render_status(db,ts):
 src=[dict(r) for r in db.execute('SELECT id,provider,name,runtime_access,copy_policy,last_status,last_sync_at FROM library_sources ORDER BY provider,name')]
 counts={r['provider']:r['c'] for r in db.execute('SELECT s.provider,count(*) c FROM library_items i JOIN library_sources s ON s.id=i.source_id GROUP BY s.provider')}
 copy={r['copy_state']:r['c'] for r in db.execute('SELECT copy_state,count(*) c FROM library_items GROUP BY copy_state')}
 domains=[dict(r) for r in db.execute('SELECT domain,state,count(*) c FROM library_item_domain_state GROUP BY domain,state ORDER BY domain,state')]
 accounting_count=db.execute('SELECT count(*) FROM accounting_document_facts').fetchone()[0]
 accounting_review={r['review_status']:r['c'] for r in db.execute('SELECT review_status,count(*) c FROM accounting_document_facts GROUP BY review_status')}
 result={'contract':'edge1.library-source-catalog.v1','generated_at':ts,'sources':len(src),'items':sum(counts.values()),'providers':counts,'copy_state':copy,'domain_state':domains,'accounting_documents':accounting_count,'accounting_review':accounting_review,'source_status':src}
 lines=['# Unified Library Source Catalog','',f'Generated: {ts}',f'Registered sources: {len(src)}',f'Catalogued items: {sum(counts.values())}','', '## Providers','']
 for provider,count in sorted(counts.items()): lines.append(f'- **{provider}** — {count} catalogued items')
 lines += ['', '## Sources','']
 for s in src: lines.append(f"- **{s['name']}** — `{s['provider']}` — access `{s['runtime_access']}` — copy `{s['copy_policy']}` — status `{s['last_status']}`")
 lines += ['', '## Accounting','', f'- Structured accounting documents: **{accounting_count}**']
 for k,v in sorted(accounting_review.items()): lines.append(f'- Review state **{k}** — {v}')
 lines += ['', '## Copy state','', *(f'- **{k}** — {v}' for k,v in sorted(copy.items())), '', 'Connector-required sources may be deferred without being unhealthy. Restricted and secret-bearing sources are intentionally not broadly indexed.']
 result['library_summary_indexed']=False
 try:
  upsert_library_document(LIB,ROOT,'operations/library-source-catalog/current.md','Unified Library Source Catalog','\n'.join(lines)+'\n')
  result['library_summary_indexed']=True
 except PermissionError:
  pass
 STATUS.parent.mkdir(parents=True,exist_ok=True); STATUS.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n'); STATUS.chmod(0o644)
 return result

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--db',default=str(CATALOG)); args=ap.parse_args(); ts=now(); p=Path(args.db); p.parent.mkdir(parents=True,exist_ok=True)
 with sqlite3.connect(p) as db:
  db.row_factory=sqlite3.Row; db.execute('PRAGMA foreign_keys=ON'); db.executescript(SCHEMA); a=bootstrap_registry(db,ts); sr=bootstrap_source_registry(db,ts); b=bootstrap_evidence(db,ts); c=link_library_documents(db,ts); db.commit(); result=render_status(db,ts)
 print(json.dumps({'contact_sources_registered':a,'library_sources_registered':sr,'evidence_items':b,'library_documents':c,'status':result},sort_keys=True))
if __name__=='__main__': main()
