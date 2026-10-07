#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re, sqlite3, hashlib
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT))
from tools.automation.automation_common import utcnow, upsert_library_document
MAINT=Path('/var/lib/edge1-contacts-maintenance/maintenance.sqlite'); STATE=Path('/var/lib/edge1-document-filing/filing.sqlite3'); LIB=Path('/var/lib/bigbird-ai-library/library.sqlite3'); STATUS=Path('/var/www/edge1-status/document-filing/status.json')
SCHEMA='''CREATE TABLE IF NOT EXISTS filed_documents(attachment_sha256 TEXT PRIMARY KEY,message_id_hash TEXT NOT NULL,filename TEXT NOT NULL,category TEXT NOT NULL,metadata_json TEXT NOT NULL,library_path TEXT NOT NULL,status TEXT NOT NULL,updated_at TEXT NOT NULL);'''

def classify(name,text):
    s=(name+' '+text[:12000]).lower()
    rules=[('invoice',('invoice','amount due','invoice number')),('statement',('statement period','account statement','balance forward')),('receipt',('receipt','payment received','paid ')),('contract',('agreement','contract','terms and conditions')),('certificate',('certificate','certification','policy number')),('correspondence',('dear ','sincerely','regards,'))]
    for cat,terms in rules:
        if sum(t in s for t in terms)>=1:return cat
    return 'general'
def metadata(category,text):
    out={}
    patterns={'invoice_number':r'(?i)invoice\s*(?:number|no\.?|#)\s*[:\-]?\s*([A-Z0-9][A-Z0-9._\-/]{2,40})','amount':r'(?i)(?:amount due|total|balance due)\s*[:\-]?\s*\$?\s*([0-9][0-9,]*(?:\.\d{2})?)','due_date':r'(?i)due date\s*[:\-]?\s*([^\n]{4,40})'}
    if category in {'invoice','statement','receipt'}:
        for k,p in patterns.items():
            m=re.search(p,text); out[k]=m.group(1).strip()[:80] if m else None
    return {k:v for k,v in out.items() if v}
def build(limit=500):
    if not MAINT.is_file(): raise RuntimeError('Contacts maintenance state unavailable')
    STATE.parent.mkdir(parents=True,exist_ok=True); counts={}; processed=0; indexed=0
    with sqlite3.connect(STATE) as st, sqlite3.connect(f'file:{MAINT}?mode=ro',uri=True) as src:
        st.executescript(SCHEMA); src.row_factory=sqlite3.Row
        rows=src.execute("SELECT attachment_sha256,message_id,filename,mime_type,text_path,extracted_chars,state FROM mail_attachment_intelligence WHERE state='text_extracted' AND text_path IS NOT NULL ORDER BY analyzed_at DESC LIMIT ?",(limit,)).fetchall()
        for r in rows:
            tp=Path(r['text_path']);
            if not tp.is_file() or not str(tp.resolve()).startswith('/var/lib/'): continue
            text=tp.read_text(errors='replace')[:200000]; category=classify(r['filename'],text); meta=metadata(category,text); source=f"operations/documents/{category}/{r['attachment_sha256']}.txt"; title=f"{category.title()} — {r['filename']}"; header=f"Document filing classification: {category}\nOriginal filename: {r['filename']}\nAttachment SHA256: {r['attachment_sha256']}\nSource message hash: {hashlib.sha256(r['message_id'].encode()).hexdigest()}\nExtracted metadata: {json.dumps(meta,sort_keys=True)}\n\n"
            upsert_library_document(LIB,ROOT,source,title,header+text)
            st.execute("""INSERT INTO filed_documents VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(attachment_sha256) DO UPDATE SET category=excluded.category,metadata_json=excluded.metadata_json,library_path=excluded.library_path,status=excluded.status,updated_at=excluded.updated_at""",(r['attachment_sha256'],hashlib.sha256(r['message_id'].encode()).hexdigest(),r['filename'],category,json.dumps(meta,sort_keys=True),source,'indexed',utcnow()))
            processed+=1; indexed+=1; counts[category]=counts.get(category,0)+1
        st.commit()
    result={'contract':'wwcx.document-filing.v1','generated_at':utcnow(),'processed':processed,'indexed':indexed,'categories':counts,'originals_moved':False,'originals_deleted':False,'classification_authoritative':False,'action_level':'AUTO-STAGE'}
    STATUS.parent.mkdir(parents=True,exist_ok=True); STATUS.write_text(json.dumps(result,indent=2)+'\n'); STATUS.chmod(0o644); return result
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--limit',type=int,default=500); a=ap.parse_args(); print(json.dumps(build(max(1,min(a.limit,2000))),sort_keys=True))
if __name__=='__main__': main()
