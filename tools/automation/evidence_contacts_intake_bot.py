#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, os, sqlite3, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
REGISTRY=ROOT/'config/contacts/contact-source-registry.json'
EVID=Path('/var/lib/edge1-evidence-intake')
INBOX=EVID/'inbox'
STAGING=EVID/'staging'
STATE=EVID/'evidence-contacts-bot.sqlite3'
CONTACTS=Path('/var/lib/edge1-phone-intelligence/phone-intelligence.sqlite')
STATUS=Path('/var/www/edge1-status/evidence-contact-intake/status.json')
SCHEMA='''CREATE TABLE IF NOT EXISTS processed(key TEXT PRIMARY KEY,digest TEXT NOT NULL,status TEXT NOT NULL,detail TEXT,processed_at TEXT NOT NULL);'''

def now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
def digest(p:Path):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
 return h.hexdigest()
def run(cmd,timeout=300):
 p=subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True,timeout=timeout)
 if p.returncode: raise RuntimeError((p.stderr or p.stdout or 'command failed')[-4000:])
 return (p.stdout or '').strip()
def seen(db,key,d):
 r=db.execute('SELECT digest,status FROM processed WHERE key=?',(key,)).fetchone()
 return bool(r and r[0]==d and r[1]=='ok')
def mark(db,key,d,status,detail=''):
 db.execute('''INSERT INTO processed(key,digest,status,detail,processed_at) VALUES(?,?,?,?,?)
 ON CONFLICT(key) DO UPDATE SET digest=excluded.digest,status=excluded.status,detail=excluded.detail,processed_at=excluded.processed_at''',(key,d,status,detail[:8000],now()))

def ingest_file(path:Path,source_system,source_name,document_type='document',verification='recovered',source_reference=None,notes=None):
 cmd=[sys.executable,str(ROOT/'tools/unified_contacts/evidence_intake.py'),'ingest-file','--path',str(path),'--source-system',source_system,'--source-name',source_name,'--document-type',document_type,'--verification-status',verification]
 if source_reference: cmd += ['--source-reference',source_reference]
 if notes: cmd += ['--notes',notes]
 return json.loads(run(cmd))

def process_inbox(db,res):
 INBOX.mkdir(parents=True,exist_ok=True)
 for p in sorted(INBOX.rglob('*')):
  if not p.is_file() or p.name.endswith('.meta.json'): continue
  d=digest(p); key='inbox:'+str(p.relative_to(INBOX))
  if seen(db,key,d): continue
  meta={}; mp=Path(str(p)+'.meta.json')
  if mp.is_file():
   try: meta=json.loads(mp.read_text())
   except Exception: meta={}
  verification=meta.get('verification_status','recovered')
  if verification not in {'recovered','verified','partial','missing'}: verification='recovered'
  try:
   out=ingest_file(p,meta.get('source_system','evidence-inbox'),meta.get('source_name',p.name),meta.get('document_type','document'),verification,meta.get('source_reference'),meta.get('notes'))
   mark(db,key,d,'ok',json.dumps(out,sort_keys=True)); res['files_preserved']+=1
  except Exception as e:
   mark(db,key,d,'error',str(e)); res['errors'].append({'source':key,'error':str(e)})

def process_local_registry(db,res):
 data=json.loads(REGISTRY.read_text())
 for s in data.get('sources',[]):
  if s.get('ingestion') not in {'enabled','enabled_existing_adapter'}: continue
  if s.get('runtime_access')!='local':
   res['connector_deferred'].append({'id':s.get('id'),'locator':s.get('locator')}); continue
  loc=s.get('locator',''); p=Path(loc if loc.startswith('/') else ROOT/loc)
  if s.get('kind')=='edge1_register' and p.is_file():
   d=digest(p); key='registry:'+s['id']
   if seen(db,key,d): continue
   try:
    out=ingest_file(p,'edge1',s['name'],'contact-register','verified',s.get('locator'),'Source registry local register snapshot.')
    mark(db,key,d,'ok',json.dumps(out,sort_keys=True));res['files_preserved']+=1
   except Exception as e:
    mark(db,key,d,'error',str(e));res['errors'].append({'source':key,'error':str(e)})
  elif p.exists(): res['local_references']+=1

def backfill_local_source_documents(dbstate,res):
 if not CONTACTS.is_file(): return
 with sqlite3.connect(f'file:{CONTACTS}?mode=ro',uri=True) as c:
  c.row_factory=sqlite3.Row
  rows=c.execute("SELECT id,document_type,source_name,source_reference,verification_status FROM source_documents WHERE sha256 IS NULL AND source_reference IS NOT NULL").fetchall()
 for r in rows:
  ref=str(r['source_reference']); p=Path(ref)
  if not p.is_absolute() or not p.is_file(): continue
  d=digest(p);key=f"source-document:{r['id']}"
  if seen(dbstate,key,d): continue
  try:
   ver='verified' if r['verification_status']=='verified' else 'recovered'
   out=ingest_file(p,'edge1-local-reference',r['source_name'],r['document_type'],ver,ref,'Automatic local source-document hash/copy backfill.')
   mark(dbstate,key,d,'ok',json.dumps(out,sort_keys=True));res['source_documents_backfilled']+=1
  except Exception as e:
   mark(dbstate,key,d,'error',str(e));res['errors'].append({'source':key,'error':str(e)})

def importer(db,key,path,cmd,res):
 if not path.is_file(): return
 d=digest(path)
 if seen(db,key,d): return
 try:
  out=run(cmd,600);mark(db,key,d,'ok',out);res['imports_run']+=1
 except Exception as e:
  mark(db,key,d,'error',str(e));res['errors'].append({'source':key,'error':str(e)})

def process_supported_imports(db,res):
 p=ROOT/'config/contacts/library-register-document-sourced-contacts-20261007.json'
 importer(db,'import:library-register',p,[sys.executable,str(ROOT/'tools/unified_contacts/import_contact_register_snapshot.py'),'--snapshot',str(p),'--commit'],res)
 p=ROOT/'config/contacts/airtable-operations-contacts-20261007.json'
 importer(db,'import:airtable-people',p,[sys.executable,str(ROOT/'tools/unified_contacts/import_airtable_contact_snapshot.py'),'--snapshot',str(p),'--commit'],res)
 snaps=sorted(STAGING.glob('airtable-organizations-*.json'),key=lambda x:x.stat().st_mtime,reverse=True)
 if snaps:
  p=snaps[0]; importer(db,'import:airtable-organizations',p,[sys.executable,str(ROOT/'tools/unified_contacts/import_airtable_organization_snapshot.py'),'--snapshot',str(p),'--commit'],res)

def downstream(res):
 if not (res['files_preserved'] or res['source_documents_backfilled'] or res['imports_run']): return
 try:
  py=ROOT/'.venv-evidence-extractor/bin/python'
  if not py.is_file(): raise RuntimeError('evidence extractor virtualenv is unavailable')
  out=run([str(py),str(ROOT/'tools/automation/evidence_document_contact_extractor.py')],600)
  res['document_extraction_ran']=True
  res['document_extraction']=json.loads(out)
 except Exception as e: res['errors'].append({'source':'document-contact-extractor','error':str(e)})
 try:
  run([sys.executable,str(ROOT/'tools/unified_contacts/maintenance_bot.py'),'--apply-safe','--json'],600);res['maintenance_ran']=True
 except Exception as e: res['errors'].append({'source':'contacts-maintenance','error':str(e)})
 try:
  run([sys.executable,str(ROOT/'tools/automation/contacts_verified_autopromote.py')],600);res['autopromote_ran']=True
 except Exception as e: res['errors'].append({'source':'contacts-autopromote','error':str(e)})

def main():
 EVID.mkdir(parents=True,exist_ok=True);STAGING.mkdir(parents=True,exist_ok=True)
 res={'contract':'edge1.evidence-contacts-intake.v1','generated_at':now(),'files_preserved':0,'source_documents_backfilled':0,'imports_run':0,'local_references':0,'connector_deferred':[],'document_extraction_ran':False,'document_extraction':None,'maintenance_ran':False,'autopromote_ran':False,'errors':[]}
 with sqlite3.connect(STATE) as db:
  db.executescript(SCHEMA)
  process_inbox(db,res);process_local_registry(db,res);backfill_local_source_documents(db,res);process_supported_imports(db,res);db.commit()
 downstream(res);res['state']='attention' if res['errors'] else ('deferred_connectors' if res['connector_deferred'] else 'healthy')
 STATUS.parent.mkdir(parents=True,exist_ok=True);STATUS.write_text(json.dumps(res,indent=2,sort_keys=True)+'\n');STATUS.chmod(0o644)
 print(json.dumps(res,sort_keys=True))
 return 1 if res['errors'] else 0
if __name__=='__main__': raise SystemExit(main())
