#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, shutil, sqlite3, sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from server.unified_contacts_crud import UnifiedContactsCrud, ContactsConflict, normalize_contact_point


def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()

def load_entries(path: Path):
    if not path.is_file(): return []
    data=json.loads(path.read_text())
    entries=data.get('entries',[]) if isinstance(data,dict) else []
    return [e for e in entries if isinstance(e,dict)]

def find_entity(db, entity_type, name):
    rows=db.execute("SELECT id FROM contact_entities WHERE entity_type=? AND lifecycle_status='active' AND lower(canonical_name)=lower(?) ORDER BY id",(entity_type,name)).fetchall()
    if len(rows)!=1:
        raise RuntimeError(f'expected exactly one active {entity_type} named {name!r}; found {len(rows)}')
    return int(rows[0][0])

def active_owners(db, point_id):
    return [int(r[0]) for r in db.execute("SELECT DISTINCT entity_id FROM contact_assertions WHERE contact_point_id=? AND assertion_type='contact' AND valid_to IS NULL",(point_id,)).fetchall()]

def provenance(db, entry, scope):
    result=[]
    for src in entry.get('sources') or []:
        if not isinstance(src,dict): continue
        name=str(src.get('name') or 'Contact resolution evidence')[:300]
        url=src.get('url') if scope=='public' else None
        ref=src.get('locator') or src.get('url') or name
        evidence=str(src.get('evidence') or entry.get('rationale') or '')
        cur=db.execute("""INSERT INTO provenance_records(source_kind,source_name,source_reference,source_url,extraction_method,verification_status,notes)
                          VALUES(?,?,?,?,?,?,?)""",
                       ('public_source' if scope=='public' else 'document',name,ref,url,
                        'phone_resolution_registry','document_sourced',evidence))
        result.append((int(cur.lastrowid),evidence,ref))
    if not result:
        cur=db.execute("""INSERT INTO provenance_records(source_kind,source_name,source_reference,extraction_method,verification_status,notes)
                          VALUES(?,?,?,?,?,?)""",
                       ('public_source' if scope=='public' else 'document','Contact resolution registry',entry.get('normalized_number'),
                        'phone_resolution_registry','document_sourced',entry.get('rationale')))
        result.append((int(cur.lastrowid),str(entry.get('rationale') or ''),str(entry.get('normalized_number') or '')))
    return result

def link_evidence(db, assertion_id, provs, summary):
    now=datetime.now(timezone.utc).isoformat(timespec='seconds')
    for pid,ev,_ in provs:
        db.execute("INSERT OR IGNORE INTO assertion_evidence(assertion_id,provenance_id,evidence_role,evidence_summary,created_at) VALUES(?,?,'supports',?,?)",
                   (assertion_id,pid,ev or summary,now))

def attest(db, entity_id, point_id, provs, attribute, value, scope, notes):
    now=datetime.now(timezone.utc).isoformat(timespec='seconds')
    for pid,_,ref in provs:
        db.execute("""INSERT INTO contact_attestations(entity_id,contact_point_id,provenance_id,attribute,attested_value,classification,verification_status,source_path,notes,created_at)
                      VALUES(?,?,?,?,?,?,?,?,?,?)""",
                   (entity_id if point_id is None else None,point_id,pid,attribute,value,
                    'public_resolution' if scope=='public' else 'restricted_internal','document_sourced',str(ref),notes,now))

def assertion_for(db, entity_id, point_id):
    row=db.execute("SELECT id FROM contact_assertions WHERE entity_id=? AND contact_point_id=? AND assertion_type='contact' AND valid_to IS NULL ORDER BY id DESC LIMIT 1",(entity_id,point_id)).fetchone()
    if not row: raise RuntimeError('expected active assertion after point add')
    return int(row[0])

def apply_entry(db, crud, entry, scope):
    if entry.get('confidence')!='document_sourced':
        return {'status':'held','reason':'confidence_not_document_sourced'}
    resolution=entry.get('resolution')
    name=str(entry.get('canonical_name') or '').strip()
    number=str(entry.get('normalized_number') or '').strip()
    if not name or not number: raise RuntimeError('resolution entry missing name/number')
    entity_type='person' if resolution=='existing_person' else 'organization'
    if resolution in {'existing_person','existing_organization'}:
        entity_id=find_entity(db,entity_type,name)
        created=False
    elif resolution=='new_organization':
        rows=db.execute("SELECT id FROM contact_entities WHERE entity_type='organization' AND lifecycle_status='active' AND lower(canonical_name)=lower(?) ORDER BY id",(name,)).fetchall()
        if len(rows)>1:
            raise RuntimeError(f'ambiguous existing organization {name!r}: {[int(r[0]) for r in rows]}')
        if len(rows)==1:
            entity_id=int(rows[0][0]); created=False
        else:
            result=crud.create_entity(entity_type='organization',canonical_name=name,display_name=name,verification_status='document_sourced',notes=entry.get('rationale'))
            entity_id=result.entity_id; created=True
    else:
        return {'status':'held','reason':'unsupported_resolution'}

    # Repeat-run guard: if the phone and every proposed coordinate are already
    # attached to the resolved entity, do not create duplicate provenance.
    expected=[('phone',number)]
    for cp in entry.get('contact_points') or []:
        if isinstance(cp,dict) and cp.get('point_type') and cp.get('value'):
            expected.append((cp['point_type'],cp['value']))
    complete=True
    for ptype,value in expected:
        norm,_=normalize_contact_point(ptype,value)
        row=db.execute("SELECT id FROM contact_points WHERE point_type=? AND normalized_value=?",(ptype,norm)).fetchone()
        if not row or entity_id not in active_owners(db,int(row[0])):
            complete=False; break
    if complete:
        return {'status':'already_applied','entity_id':entity_id,'entity_created':False}

    point=db.execute("SELECT id FROM contact_points WHERE point_type='phone' AND normalized_value=?",(number,)).fetchone()
    if point:
        owners=active_owners(db,int(point[0]))
        if owners and entity_id not in owners:
            raise RuntimeError(f'phone {number} already owned by different entity ids {owners}')
    try:
        result=crud.add_contact_point(entity_id=entity_id,point_type='phone',value=number,
                                      classification='public_resolution' if scope=='public' else 'restricted_internal',
                                      confidence='document_sourced',assertion_notes=entry.get('rationale'))
        phone_point_id=result.contact_point_id
    except ContactsConflict as exc:
        if 'already attached' not in str(exc): raise
        phone_point_id=int(db.execute("SELECT id FROM contact_points WHERE point_type='phone' AND normalized_value=?",(number,)).fetchone()[0])
    phone_assertion=assertion_for(db,entity_id,phone_point_id)
    provs=provenance(db,entry,scope)
    link_evidence(db,phone_assertion,provs,entry.get('rationale') or '')
    attest(db,None,phone_point_id,provs,'phone',number,scope,entry.get('rationale'))
    if created:
        attest(db,entity_id,None,provs,'canonical_name',name,scope,entry.get('rationale'))

    added=[]
    for cp in entry.get('contact_points') or []:
        if not isinstance(cp,dict): continue
        ptype=cp.get('point_type'); value=cp.get('value')
        if not ptype or not value: continue
        try:
            r=crud.add_contact_point(entity_id=entity_id,point_type=ptype,value=value,classification='public_resolution',confidence='document_sourced',assertion_notes=entry.get('rationale'))
            pid=r.contact_point_id
        except ContactsConflict as exc:
            if 'already attached' not in str(exc): raise
            norm,_=normalize_contact_point(ptype,value)
            row=db.execute("SELECT id FROM contact_points WHERE point_type=? AND normalized_value=?",(ptype,norm)).fetchone()
            if not row: raise
            pid=int(row[0])
        owners=active_owners(db,pid)
        if any(owner!=entity_id for owner in owners):
            raise RuntimeError(f'{ptype} {value!r} is owned by another entity {owners}')
        aid=assertion_for(db,entity_id,pid)
        link_evidence(db,aid,provs,entry.get('rationale') or '')
        attest(db,None,pid,provs,ptype,str(value),scope,entry.get('rationale'))
        added.append({'point_type':ptype,'contact_point_id':pid})
    return {'status':'applied','entity_id':entity_id,'entity_created':created,'phone_point_id':phone_point_id,'additional_points':added}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--database',default='/var/lib/edge1-phone-intelligence/phone-intelligence.sqlite')
    ap.add_argument('--public-registry',default='config/contacts/public-phone-resolutions.json')
    ap.add_argument('--internal-registry',default='config/contacts/internal-phone-resolutions.json')
    ap.add_argument('--backup-dir',default='/var/lib/edge1-contacts-maintenance/backups')
    ap.add_argument('--commit',action='store_true')
    a=ap.parse_args(); dbp=Path(a.database); before=sha256(dbp); backup=None
    if a.commit:
        bd=Path(a.backup_dir); bd.mkdir(parents=True,exist_ok=True)
        stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        backup=bd/f'phone-intelligence-before-resolution-apply-{stamp}.sqlite'
        shutil.copy2(dbp,backup)
        if sha256(backup)!=before: raise RuntimeError('backup hash mismatch')
    db=sqlite3.connect(dbp,timeout=15); db.row_factory=sqlite3.Row; db.execute('PRAGMA foreign_keys=ON')
    results=[]
    try:
        db.execute('BEGIN IMMEDIATE' if a.commit else 'BEGIN')
        crud=UnifiedContactsCrud(db)
        for scope,path in [('public',Path(a.public_registry)),('internal',Path(a.internal_registry))]:
            for entry in load_entries(path):
                try:
                    result=apply_entry(db,crud,entry,scope)
                except Exception as exc:
                    result={'status':'error','error':str(exc)}
                    if entry.get('confidence')=='document_sourced': raise
                results.append({'scope':scope,'number':entry.get('normalized_number'),'name':entry.get('canonical_name'),**result})
        integrity=db.execute('PRAGMA integrity_check').fetchone()[0]; fk=db.execute('PRAGMA foreign_key_check').fetchall()
        if integrity!='ok' or fk: raise RuntimeError(f'database verification failed integrity={integrity} fk={fk[:5]}')
        if a.commit: db.commit()
        else: db.rollback()
    except Exception:
        db.rollback(); raise
    finally: db.close()
    print(json.dumps({'transaction':'COMMITTED' if a.commit else 'ROLLED_BACK','backup':str(backup) if backup else None,'sha_before':before,'sha_after':sha256(dbp),'results':results},indent=2,sort_keys=True))

if __name__=='__main__': main()
