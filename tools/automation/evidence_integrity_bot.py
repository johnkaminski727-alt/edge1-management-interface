#!/usr/bin/env python3
from __future__ import annotations
import json, sqlite3
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse
import sys
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT))
from tools.automation.automation_common import utcnow, upsert_library_document
LIB=Path('/var/lib/bigbird-ai-library/library.sqlite3'); CONTACTS=Path('/var/lib/edge1-phone-intelligence/phone-intelligence.sqlite')
STATUS=Path('/var/www/edge1-status/evidence-integrity/status.json')
def is_url(v): return urlparse(str(v)).scheme in {'http','https'}
def build():
    findings=[]; lib_counts=Counter(); contact_counts=Counter()
    if LIB.is_file():
        with sqlite3.connect(f'file:{LIB}?mode=ro',uri=True) as db:
            for title,source in db.execute('SELECT title,source_path FROM documents'):
                source=str(source or '')
                if not source: lib_counts['missing_reference']+=1; findings.append({'system':'private_library','severity':'medium','title':title,'reference':source,'issue':'missing_reference'}); continue
                if is_url(source): lib_counts['declared_url']+=1; continue
                if source.startswith('operations/') or source.startswith('mail-attachments/'): lib_counts['logical_internal']+=1; continue
                p=Path(source) if Path(source).is_absolute() else ROOT/source
                if p.exists(): lib_counts['local_verified']+=1
                else: lib_counts['local_missing']+=1; findings.append({'system':'private_library','severity':'medium','title':title,'reference':source,'issue':'local_source_missing'})
    else: findings.append({'system':'private_library','severity':'high','title':'Private Library','reference':str(LIB),'issue':'database_missing'})
    if CONTACTS.is_file():
        with sqlite3.connect(f'file:{CONTACTS}?mode=ro',uri=True) as db:
            db.row_factory=sqlite3.Row
            try: rows=db.execute('SELECT provenance_id,location_kind,location,verification_status,last_verified_at FROM provenance_source_locations').fetchall()
            except sqlite3.Error: rows=[]
            for r in rows:
                status=str(r['verification_status'] or 'unknown'); contact_counts[status]+=1
                if status in {'missing','ambiguous'}: findings.append({'system':'contacts','severity':'high' if status=='ambiguous' else 'medium','title':f"provenance_id={r['provenance_id']}",'reference':r['location'],'issue':status})
                elif status=='candidate': findings.append({'system':'contacts','severity':'low','title':f"provenance_id={r['provenance_id']}",'reference':r['location'],'issue':'candidate_location'})
    else: findings.append({'system':'contacts','severity':'high','title':'Unified Contacts','reference':str(CONTACTS),'issue':'database_missing'})
    state='attention' if any(x['severity']=='high' for x in findings) else 'warning' if findings else 'healthy'
    return {'contract':'wwcx.evidence-integrity.v1','generated_at':utcnow(),'state':state,'summary':{'findings':len(findings),'high':sum(x['severity']=='high' for x in findings),'private_library':dict(lib_counts),'contacts_locations':dict(contact_counts)},'findings':findings[:300],'evidence_mutation_performed':False}
def markdown(d):
    lines=['# Evidence Integrity','',f"Generated: {d['generated_at']}",f"State: **{d['state']}**",f"Findings: {d['summary']['findings']}",'','## Findings','']; lines += [f"- **{x['system']} · {x['issue']}** — {x['title']} — `{x['reference']}`" for x in d['findings']] or ['- None.']; lines += ['','This audit never rewrites source locations or evidence records.']; return '\n'.join(lines)+'\n'
def main():
    d=build(); STATUS.parent.mkdir(parents=True,exist_ok=True); STATUS.write_text(json.dumps(d,indent=2)+'\n'); STATUS.chmod(0o644); upsert_library_document(LIB,ROOT,'operations/evidence-integrity/current.md','Evidence Integrity',markdown(d)); print(json.dumps(d['summary'],sort_keys=True))
if __name__=='__main__':main()
