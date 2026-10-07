#!/usr/bin/env python3
from __future__ import annotations
import json, sqlite3
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT))
from tools.automation.automation_common import utcnow, upsert_library_document
FILING=Path('/var/lib/edge1-document-filing/filing.sqlite3')
STATE=Path('/var/lib/edge1-accounting-intake/intake.sqlite3')
STATUS=Path('/var/www/edge1-status/accounting-intake/status.json')
LIB=Path('/var/lib/bigbird-ai-library/library.sqlite3')
SCHEMA='''
CREATE TABLE IF NOT EXISTS accounting_items(
 attachment_sha256 TEXT PRIMARY KEY,
 message_id_hash TEXT NOT NULL,
 filename TEXT NOT NULL,
 category TEXT NOT NULL,
 invoice_number TEXT,
 amount TEXT,
 due_date TEXT,
 library_path TEXT NOT NULL,
 review_status TEXT NOT NULL,
 duplicate_group TEXT,
 first_seen_at TEXT NOT NULL,
 updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_accounting_review ON accounting_items(review_status,category);
'''

def build():
    if not FILING.is_file(): raise RuntimeError('document filing state unavailable')
    STATE.parent.mkdir(parents=True,exist_ok=True); now=utcnow(); staged=0
    with sqlite3.connect(f'file:{FILING}?mode=ro',uri=True) as src, sqlite3.connect(STATE) as dst:
        src.row_factory=sqlite3.Row; dst.row_factory=sqlite3.Row; dst.executescript(SCHEMA)
        rows=src.execute("SELECT attachment_sha256,message_id_hash,filename,category,metadata_json,library_path FROM filed_documents WHERE category IN ('invoice','statement','receipt') AND status='indexed' ORDER BY updated_at DESC").fetchall()
        for r in rows:
            try: meta=json.loads(r['metadata_json'] or '{}')
            except Exception: meta={}
            review='review_required' if r['category']=='invoice' else 'staged'
            dst.execute('''INSERT INTO accounting_items(attachment_sha256,message_id_hash,filename,category,invoice_number,amount,due_date,library_path,review_status,duplicate_group,first_seen_at,updated_at)
              VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(attachment_sha256) DO UPDATE SET filename=excluded.filename,category=excluded.category,invoice_number=excluded.invoice_number,amount=excluded.amount,due_date=excluded.due_date,library_path=excluded.library_path,updated_at=excluded.updated_at''',
              (r['attachment_sha256'],r['message_id_hash'],r['filename'],r['category'],meta.get('invoice_number'),meta.get('amount'),meta.get('due_date'),r['library_path'],review,None,now,now)); staged+=1
        # Duplicate grouping is advisory only: same invoice number+amount on distinct attachment hashes.
        groups=dst.execute("""SELECT lower(invoice_number),amount,group_concat(attachment_sha256),count(*) FROM accounting_items
          WHERE invoice_number IS NOT NULL AND amount IS NOT NULL GROUP BY lower(invoice_number),amount HAVING count(*)>1""").fetchall()
        duplicate_items=0
        for inv,amount,hashes,count in groups:
            key=f'{inv}|{amount}'
            for digest in hashes.split(','):
                dst.execute("UPDATE accounting_items SET duplicate_group=?,review_status='possible_duplicate',updated_at=? WHERE attachment_sha256=?",(key,now,digest)); duplicate_items+=1
        counts={r[0]:r[1] for r in dst.execute('SELECT category,count(*) FROM accounting_items GROUP BY category')}
        statuses={r[0]:r[1] for r in dst.execute('SELECT review_status,count(*) FROM accounting_items GROUP BY review_status')}
        sample=[dict(r) for r in dst.execute("SELECT attachment_sha256,filename,category,invoice_number,amount,due_date,library_path,review_status FROM accounting_items ORDER BY updated_at DESC LIMIT 50")]
        dst.commit()
    result={'contract':'wwcx.accounting-intake.v1','generated_at':now,'state':'attention' if statuses.get('review_required',0) or statuses.get('possible_duplicate',0) else 'healthy','items':sum(counts.values()),'categories':counts,'review_status':statuses,'possible_duplicate_items':duplicate_items,'sample':sample,'payment_authorized':False,'bank_mutation_authorized':False,'action_level':'AUTO-STAGE'}
    STATUS.parent.mkdir(parents=True,exist_ok=True); STATUS.write_text(json.dumps(result,indent=2)+'\n'); STATUS.chmod(0o644)
    lines=['# Accounting Intake','',f"Generated: {now}",f"Items: {result['items']}",f"Categories: {json.dumps(counts,sort_keys=True)}",f"Review status: {json.dumps(statuses,sort_keys=True)}",'', '## Review queue','']
    for x in sample:
        if x['review_status'] in {'review_required','possible_duplicate'}:
            lines.append(f"- **{x['filename']}** — {x['category']} — invoice `{x['invoice_number'] or 'unknown'}` — amount `{x['amount'] or 'unknown'}` — due `{x['due_date'] or 'unknown'}` — {x['review_status']} — evidence `{x['library_path']}`")
    if len(lines)==8: lines.append('- No accounting items currently require review.')
    lines += ['','This intake is advisory/staging only. It cannot initiate payments or alter bank/accounting systems.']
    upsert_library_document(LIB,ROOT,'operations/accounting-intake/current.md','Current Accounting Intake','\n'.join(lines)+'\n')
    return result
if __name__=='__main__':
    d=build(); print(json.dumps({k:d[k] for k in ('state','items','categories','review_status','possible_duplicate_items')},sort_keys=True))
