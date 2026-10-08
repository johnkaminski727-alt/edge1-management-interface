#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re, sqlite3, sys
from datetime import datetime, timezone
from pathlib import Path

DB=Path('/var/lib/edge1-phone-intelligence/phone-intelligence.sqlite')
EVID=Path('/var/lib/edge1-evidence-intake/objects')

PHONE_RE=re.compile(r'(?<!\d)(?:\+?1[\s().-]*)?(\d{3})[\s().-]*(\d{3})[\s.-]*(\d{4})(?!\d)')

def normalize_phone(v:str)->str:
    d=''.join(ch for ch in v if ch.isdigit())
    if len(d)==10: d='1'+d
    if len(d)!=11 or not d.startswith('1'): raise ValueError('unsupported phone format')
    return '+'+d

def source_path(row):
    digest=row['sha256']; name=row['source_name']
    return EVID/digest[:2]/digest/name

def one_org(db,name):
    rows=db.execute("SELECT id FROM contact_entities WHERE entity_type='organization' AND lower(canonical_name)=lower(?) AND lifecycle_status='active' ORDER BY id",(name,)).fetchall()
    if len(rows)!=1: return None
    return int(rows[0][0])

def provenance(db,row):
    rows=db.execute("SELECT id FROM provenance_records WHERE source_document_id=? AND extraction_method='document-contact-extractor-v1' ORDER BY id",(row['id'],)).fetchall()
    if rows: return int(rows[0][0])
    cur=db.execute('''INSERT INTO provenance_records(source_document_id,source_kind,source_name,source_reference,source_sha256,extraction_method,verification_status,notes)
      VALUES(?,?,?,?,?,'document-contact-extractor-v1','document_sourced',?)''',
      (row['id'],'document',row['source_name'],row['source_reference'],row['sha256'],'Extracted automatically from preserved verified document; role-sensitive rules applied.'))
    return int(cur.lastrowid)

def point(db,ptype,normalized,display,classification):
    rows=db.execute('SELECT id FROM contact_points WHERE point_type=? AND normalized_value=? ORDER BY id',(ptype,normalized)).fetchall()
    if rows:
        pid=int(rows[0][0]); db.execute("UPDATE contact_points SET display_value=COALESCE(display_value,?), classification=COALESCE(classification,?), updated_at=CURRENT_TIMESTAMP WHERE id=?",(display,classification,pid)); return pid,False
    cur=db.execute('''INSERT INTO contact_points(point_type,normalized_value,display_value,classification,lifecycle_status) VALUES(?,?,?,?,'active')''',(ptype,normalized,display,classification))
    return int(cur.lastrowid),True

def attest(db,pid,prov,attribute,value,classification,source_id):
    rows=db.execute('''SELECT id FROM contact_attestations WHERE contact_point_id=? AND provenance_id=? AND attribute=? AND attested_value=? ORDER BY id''',(pid,prov,attribute,value)).fetchall()
    if rows: return False
    db.execute('''INSERT INTO contact_attestations(entity_id,contact_point_id,provenance_id,attribute,attested_value,classification,verification_status,source_path,notes)
      VALUES(NULL,?,?,?,?,?,'document_sourced',?,?)''',(pid,prov,attribute,value,classification,f'source_document:{source_id}','Role determined from explicit document labelling; preserved source hash retained in provenance.'))
    return True

def assert_contact(db,entity_id,pid,notes):
    owners=db.execute("SELECT entity_id FROM contact_assertions WHERE contact_point_id=? AND valid_to IS NULL ORDER BY id",(pid,)).fetchall()
    owner_ids={int(r[0]) for r in owners}
    if owner_ids and owner_ids!={entity_id}:
        return False,'ownership_conflict'
    if entity_id in owner_ids: return False,'existing'
    db.execute('''INSERT INTO contact_assertions(entity_id,contact_point_id,assertion_type,confidence,notes) VALUES(?,?,'contact','document_sourced',?)''',(entity_id,pid,notes))
    return True,'created'

def extract_text(pdf:Path):
    from pypdf import PdfReader
    r=PdfReader(str(pdf)); pages=[]
    for i,p in enumerate(r.pages,1): pages.append((i,p.extract_text() or ''))
    return pages

def sasktel_facts(pages):
    text='\n'.join(t for _,t in pages)
    compact=' '.join(text.split())
    facts=[]
    # Explicit SaskTel sales/service/support/billing number. This is safe to attach to SaskTel.
    if re.search(r'(?:sales|service|support|billing).{0,80}(?:1\s*800\s*727[-\s]*5835|1\s*800\s*SaskTel)',compact,re.I):
        facts.append({'kind':'organization_phone','organization':'SaskTel','value':'+18007275835','display':'1 800 727-5835','classification':'sales_service_support_billing'})
    # Numbers explicitly presented as covered/billed/service lines remain unowned observations.
    for m in PHONE_RE.finditer(text):
        raw=m.group(0); norm=normalize_phone(raw)
        start=max(0,m.start()-100); end=min(len(text),m.end()+100); ctx=' '.join(text[start:end].split()).lower()
        if norm=='+18007275835': continue
        if any(x in ctx for x in ['ccts','commission for complaints','1-888-221-1687']): continue
        if any(x in ctx for x in ['phone numbers','numbers covered by this bill','call taking charge for','telecommunications fee for','internet charges','for 306']):
            facts.append({'kind':'service_phone','value':norm,'display':raw.strip(),'classification':'billed_service_number'})
    # de-dupe
    out=[]; seen=set()
    for f in facts:
        k=(f['kind'],f['value'],f.get('organization'))
        if k not in seen: seen.add(k); out.append(f)
    return out

def process(db,row,dry_run=False):
    p=source_path(row)
    if not p.is_file(): return {'source_document_id':row['id'],'status':'missing_local_copy','facts':[]}
    if p.suffix.lower()!='.pdf': return {'source_document_id':row['id'],'status':'unsupported_type','facts':[]}
    pages=extract_text(p)
    name=(row['source_name'] or '').lower()
    if 'sasktel' not in name:
        return {'source_document_id':row['id'],'status':'no_adapter','facts':[]}
    facts=sasktel_facts(pages)
    result={'source_document_id':row['id'],'status':'ok','facts':facts,'applied':0,'deferred':0}
    if dry_run or not facts: return result
    prov=provenance(db,row)
    for f in facts:
        pid,_=point(db,'phone',f['value'],f['display'],f['classification'])
        if f['kind']=='organization_phone':
            eid=one_org(db,f['organization'])
            if not eid:
                result['deferred']+=1; continue
            attest(db,pid,prov,'organization_phone',f['value'],f['classification'],row['id'])
            made,status=assert_contact(db,eid,pid,f"Verified document {row['id']} explicitly labels this as {f['organization']} sales/service/support/billing contact.")
            result['applied']+=int(made)
            if status=='ownership_conflict': result['deferred']+=1
        else:
            made=attest(db,pid,prov,'billed_service_phone',f['value'],f['classification'],row['id'])
            result['applied']+=int(made)
    return result

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--database',default=str(DB)); ap.add_argument('--source-document-id',type=int); ap.add_argument('--dry-run',action='store_true'); args=ap.parse_args()
    db=sqlite3.connect(args.database); db.row_factory=sqlite3.Row; db.execute('PRAGMA foreign_keys=ON')
    q="SELECT * FROM source_documents WHERE verification_status='verified' AND sha256 IS NOT NULL AND document_type IN ('telecom-bill','telecom-statement','document','statement','bill')"
    vals=()
    if args.source_document_id:
        q+=' AND id=?'
        vals=(args.source_document_id,)
    rows=db.execute(q+' ORDER BY id',vals).fetchall(); out=[]
    backup=None
    if rows and not args.dry_run:
        backup_dir=Path('/var/lib/edge1-contacts-maintenance/backups'); backup_dir.mkdir(parents=True,exist_ok=True)
        backup=backup_dir/f"phone-intelligence-before-document-contact-extract-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.sqlite"
        b=sqlite3.connect(backup)
        try: db.backup(b)
        finally: b.close()
    try:
        db.execute('BEGIN IMMEDIATE' if not args.dry_run else 'BEGIN')
        for r in rows: out.append(process(db,r,args.dry_run))
        if args.dry_run: db.rollback()
        else: db.commit()
    except Exception:
        db.rollback(); raise
    finally: db.close()
    print(json.dumps({'documents':len(out),'results':out,'backup':str(backup) if backup else None},sort_keys=True))
if __name__=='__main__': main()
