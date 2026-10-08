#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re, sqlite3
from datetime import datetime, timezone
from pathlib import Path

CATALOG=Path('/var/lib/bigbird-ai-library/catalog/source-catalog.sqlite3')
STATUS=Path('/var/www/edge1-status/library-accounting/status.json')

def now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
def money(text):
 if text is None: return None
 return text.replace(',','').strip()
def extract_text(path:Path):
 if path.suffix.lower()!='.pdf': return path.read_text(errors='replace')[:500000]
 from pypdf import PdfReader
 return '\n'.join((p.extract_text() or '') for p in PdfReader(str(path)).pages)[:500000]
def first(pattern,text,flags=re.I|re.M):
 m=re.search(pattern,text,flags); return m.group(1).strip() if m else None
def infer_kind(title,item_type,text):
 s=f'{title} {item_type} {text[:4000]}'.lower()
 if 'credit card statement' in s: return 'credit_card_statement'
 if 'bank statement' in s: return 'bank_statement'
 if 'mobility' in s and 'statement' in s: return 'telecom_statement'
 if 'statement' in s: return 'statement'
 if 'invoice' in s: return 'invoice'
 if 'receipt' in s: return 'receipt'
 if 'bill' in s: return 'bill'
 return None
def vendor(title,text):
 s=(title+' '+text[:12000]).lower()
 if 'sasktel' in s: return 'SaskTel'
 return None
def issue_date(title,text):
 m=re.match(r'(20\d{2}-\d{2}-\d{2})',title)
 if m:return m.group(1)
 return None
def extract_facts(row,text):
 title=row['title']; kind=infer_kind(title,row['item_type'],text); v=vendor(title,text)
 if not kind: return None
 account=first(r'Account\s*(?:number|#)\s*[:\-]?\s*([A-Z0-9][A-Z0-9\- ]{3,30})',text)
 total=first(r'Total\s*amount\s*due(?:\s*as\s*of\s*the\s*bill\s*date)?\s*\$\s*([0-9][0-9,]*\.\d{2})',text)
 if not total: total=first(r'(?:Amount\s+Due|Total\s+Due)\s*[:\-]?\s*\$\s*([0-9][0-9,]*\.\d{2})',text)
 due=first(r'Due\s+date\s*[:\-]?\s*([^\n]{4,40})',text)
 currency='CAD' if ('$' in text and (v=='SaskTel' or ' canada' in text.lower() or ' sk ' in text.lower())) else None
 return {'vendor_name':v,'document_kind':kind,'issue_date':issue_date(title,text),'account_reference':account,'currency':currency,'total_amount':money(total),'balance_due':money(total),'due_date':due,'extraction_confidence':'document_sourced' if v or account or total else 'low','review_status':'staged' if v or account or total else 'review_required'}
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--limit',type=int,default=100); ap.add_argument('--dry-run',action='store_true'); a=ap.parse_args()
 if not CATALOG.is_file(): raise SystemExit('source catalog unavailable')
 out=[]; processed=0; skipped=0
 with sqlite3.connect(CATALOG) as db:
  db.row_factory=sqlite3.Row; db.execute('PRAGMA foreign_keys=ON')
  rows=db.execute('''SELECT i.*,d.state domain_state FROM library_items i JOIN library_item_domain_state d ON d.item_id=i.id AND d.domain='accounting' WHERE i.local_path IS NOT NULL AND i.copy_state='preserved' AND d.state IN ('pending','retry') ORDER BY i.last_seen_at LIMIT ?''',(max(1,min(a.limit,1000)),)).fetchall()
  for r in rows:
   p=Path(r['local_path'])
   if not p.is_file(): skipped+=1; continue
   try: text=extract_text(p)
   except Exception as e:
    if not a.dry_run: db.execute("UPDATE library_item_domain_state SET state='retry',processor_version='accounting-v1',last_processed_at=?,detail_json=? WHERE item_id=?",(now(),json.dumps({'error':str(e)})[:4000],r['id']))
    out.append({'item_id':r['id'],'status':'retry','error':str(e)}); continue
   f=extract_facts(r,text)
   if not f:
    if not a.dry_run: db.execute("UPDATE library_item_domain_state SET state='not_applicable',processor_version='accounting-v1',last_processed_at=?,detail_json=? WHERE item_id=?",(now(),json.dumps({'reason':'not accounting document'}),r['id']))
    skipped+=1; continue
   if not a.dry_run:
    db.execute('''INSERT INTO accounting_document_facts(item_id,vendor_name,document_kind,issue_date,account_reference,currency,total_amount,balance_due,due_date,extraction_confidence,review_status,source_sha256,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(item_id) DO UPDATE SET vendor_name=excluded.vendor_name,document_kind=excluded.document_kind,issue_date=excluded.issue_date,account_reference=excluded.account_reference,currency=excluded.currency,total_amount=excluded.total_amount,balance_due=excluded.balance_due,due_date=excluded.due_date,extraction_confidence=excluded.extraction_confidence,review_status=excluded.review_status,source_sha256=excluded.source_sha256,updated_at=excluded.updated_at''',(r['id'],f['vendor_name'],f['document_kind'],f['issue_date'],f['account_reference'],f['currency'],f['total_amount'],f['balance_due'],f['due_date'],f['extraction_confidence'],f['review_status'],r['content_sha256'],now()))
    db.execute("UPDATE library_item_domain_state SET state='processed',processor_version='accounting-v1',last_processed_at=?,detail_json=? WHERE item_id=?",(now(),json.dumps(f,sort_keys=True),r['id']))
   processed+=1; out.append({'item_id':r['id'],'title':r['title'],'facts':f})
  if not a.dry_run: db.commit()
 with sqlite3.connect(CATALOG) as statdb:
  structured_total=statdb.execute('SELECT count(*) FROM accounting_document_facts').fetchone()[0]
  review_counts={r[0]:r[1] for r in statdb.execute('SELECT review_status,count(*) FROM accounting_document_facts GROUP BY review_status')}
 result={'contract':'edge1.library-accounting-extractor.v1','generated_at':now(),'processed':processed,'skipped':skipped,'structured_total':structured_total,'review_status':review_counts,'dry_run':a.dry_run,'items':out}
 if not a.dry_run:
  STATUS.parent.mkdir(parents=True,exist_ok=True); STATUS.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n'); STATUS.chmod(0o644)
 print(json.dumps(result,sort_keys=True))
if __name__=='__main__': main()
