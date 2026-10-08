#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, sqlite3, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path('/opt/edge1-management-interface')
CATALOG=Path('/var/lib/bigbird-ai-library/catalog/source-catalog.sqlite3')
LIB=Path('/var/lib/bigbird-ai-library/library.sqlite3')
SOURCE_REGISTRY=ROOT/'config/private-library/source-catalog.json'
STATUS=Path('/var/www/edge1-status/library-external-index/status.json')
sys.path.insert(0,str(ROOT))
from tools.automation.automation_common import upsert_library_document

def now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
def allowed_sources():
 if not SOURCE_REGISTRY.is_file(): return set()
 data=json.loads(SOURCE_REGISTRY.read_text())
 return {s['id'] for s in data.get('sources',[]) if s.get('enabled',True) and s.get('classification')!='restricted'}
def text_for(path:Path):
 ext=path.suffix.lower()
 if ext=='.pdf':
  from pypdf import PdfReader
  return '\n'.join((p.extract_text() or '') for p in PdfReader(str(path)).pages)
 if ext in {'.txt','.md','.json','.csv','.log','.xml','.html','.htm'}:
  return path.read_text(errors='replace')
 return ''
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--limit',type=int,default=100); ap.add_argument('--dry-run',action='store_true'); a=ap.parse_args()
 allowed=allowed_sources(); indexed=0; unchanged=0; skipped=0; errors=[]; items=[]
 if not CATALOG.is_file() or not LIB.is_file(): raise SystemExit('catalog or Private Library unavailable')
 with sqlite3.connect(CATALOG) as db:
  db.row_factory=sqlite3.Row
  q='''SELECT i.*,s.provider,s.classification,s.sensitivity FROM library_items i JOIN library_sources s ON s.id=i.source_id WHERE i.local_path IS NOT NULL AND i.copy_state='preserved' ORDER BY i.last_seen_at LIMIT ?'''
  rows=db.execute(q,(max(1,min(a.limit,1000)),)).fetchall()
  for r in rows:
   if r['source_id'] not in allowed: skipped+=1; continue
   p=Path(r['local_path'])
   if not p.is_file(): skipped+=1; continue
   try: text=text_for(p)
   except Exception as e: errors.append({'item_id':r['id'],'error':str(e)}); continue
   if not text.strip():
    text=(f"External evidence document metadata.\nTitle: {r['title']}\nProvider: {r['provider']}\nSource: {r['source_id']}\nEvidence source document ID: {r['evidence_source_document_id'] or 'none'}\nSHA-256: {r['content_sha256'] or 'unavailable'}\nText extraction: unavailable; original preserved separately.\n")
   source_path=f"external/{r['provider']}/{r['source_id']}/{r['id']}"
   doc_id=hashlib.sha256(source_path.encode()).hexdigest()
   if r['library_document_id']==doc_id:
    unchanged+=1; continue
   if a.dry_run:
    items.append({'item_id':r['id'],'title':r['title'],'source_path':source_path,'chars':len(text)}); indexed+=1; continue
   try:
    result=upsert_library_document(LIB,ROOT,source_path,r['title'],text,classification=r['classification'] or 'internal')
    db.execute('UPDATE library_items SET library_document_id=?,indexed_at=?,sync_state=? WHERE id=?',(doc_id,now(),'current',r['id']))
    indexed+=1; items.append({'item_id':r['id'],'title':r['title'],'library_document_id':doc_id,'chunks':result['chunks']})
   except Exception as e:
    errors.append({'item_id':r['id'],'title':r['title'],'error':str(e)})
  if not a.dry_run: db.commit()
 result={'contract':'edge1.private-library-external-index.v1','generated_at':now(),'indexed':indexed,'unchanged':unchanged,'skipped':skipped,'errors':errors,'items':items,'dry_run':a.dry_run}
 if not a.dry_run:
  STATUS.parent.mkdir(parents=True,exist_ok=True); STATUS.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n'); STATUS.chmod(0o644)
 print(json.dumps(result,sort_keys=True))
 return 1 if errors else 0
if __name__=='__main__': raise SystemExit(main())
