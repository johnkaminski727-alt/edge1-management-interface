#!/usr/bin/env python3
"""Import evidence-backed contact-register rows into Unified Contacts."""
from __future__ import annotations

import argparse, hashlib, json, shutil, sqlite3, sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.unified_contacts.schema_contacts_expansion import apply_schema
from tools.unified_contacts.schema_connections import migrate as migrate_connections, harden as harden_connections
from tools.unified_contacts.identity_gate import require_safe_entity_resolution


def sha256(path: Path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()


def provenance(db, source):
    rows=db.execute("""SELECT id FROM provenance_records WHERE source_kind=? AND source_name=?
        AND COALESCE(source_reference,'')=? AND COALESCE(extraction_method,'')=? ORDER BY id""",
        (source['source_kind'],source['source_name'],source.get('source_reference',''),source.get('extraction_method',''))).fetchall()
    if len(rows)>1: raise RuntimeError('ambiguous provenance')
    if rows: return rows[0][0],False
    cur=db.execute("""INSERT INTO provenance_records(source_kind,source_name,source_reference,
        extraction_method,verification_status,notes) VALUES(?,?,?,?,?,?)""",
        (source['source_kind'],source['source_name'],source.get('source_reference'),source.get('extraction_method'),
         source.get('verification_status','document_sourced'),'Evidence-backed contact register import.'))
    return cur.lastrowid,True


def entity(db, typ, name, verification='document_sourced', source_record_id=None):
    entity_id, should_create, match = require_safe_entity_resolution(
        db, typ, name, source_record_id=source_record_id
    )
    if not should_create:
        return entity_id,False
    cur=db.execute("INSERT INTO contact_entities(entity_type,canonical_name,display_name,verification_status) VALUES(?,?,?,?)",
                   (typ,name,name,verification))
    return cur.lastrowid,True


def point(db, p):
    rows=db.execute("SELECT id FROM contact_points WHERE point_type=? AND normalized_value=? ORDER BY id",(p['type'],p['value'])).fetchall()
    if len(rows)>1: raise RuntimeError(f"duplicate contact point {p['type']} {p['value']}")
    if rows: return rows[0][0],False
    cur=db.execute("INSERT INTO contact_points(point_type,normalized_value,display_value,classification) VALUES(?,?,?,?)",
                   (p['type'],p['value'],p.get('display') or p['value'],p.get('classification')))
    return cur.lastrowid,True


def assertion(db,eid,pid,confidence,notes):
    row=db.execute("SELECT id FROM contact_assertions WHERE entity_id=? AND contact_point_id=? AND assertion_type='contact'",(eid,pid)).fetchone()
    if row: return row[0],False
    cur=db.execute("INSERT INTO contact_assertions(entity_id,contact_point_id,assertion_type,confidence,notes) VALUES(?,?,'contact',?,?)",
                   (eid,pid,confidence,notes))
    return cur.lastrowid,True


def evidence(db,aid,prid,summary):
    row=db.execute("SELECT id FROM assertion_evidence WHERE assertion_id=? AND provenance_id=? AND evidence_role='supports'",(aid,prid)).fetchone()
    if row: return False
    db.execute("INSERT INTO assertion_evidence(assertion_id,provenance_id,evidence_role,evidence_summary) VALUES(?,?,'supports',?)",(aid,prid,summary))
    return True


def attestation(db,eid,prid,attribute,value,source_path,classification='register_field'):
    if not value: return False
    row=db.execute("""SELECT id FROM contact_attestations WHERE entity_id=? AND contact_point_id IS NULL AND provenance_id=?
       AND attribute=? AND attested_value=? AND COALESCE(source_path,'')=?""",(eid,prid,attribute,str(value),source_path)).fetchone()
    if row: return False
    db.execute("""INSERT INTO contact_attestations(entity_id,provenance_id,attribute,attested_value,classification,
       verification_status,source_path,notes) VALUES(?,?,?,?,?,'document_sourced',?,?)""",
       (eid,prid,attribute,str(value),classification,source_path,'Imported from document-sourced contact register row.'))
    return True


def relation(db,left,right,prid,relation_type,notes):
    row=db.execute("""SELECT id FROM contact_relationships WHERE left_entity_id=? AND right_entity_id=?
       AND relationship_type=? AND lifecycle_status='active'""",(left,right,relation_type)).fetchone()
    created=False
    if row: rid=row[0]
    else:
        cur=db.execute("""INSERT INTO contact_relationships(left_entity_id,right_entity_id,relationship_type,
           confidence,lifecycle_status,directionality,notes) VALUES(?,?,?,'document_sourced','active','directed',?)""",
           (left,right,relation_type,notes)); rid=cur.lastrowid; created=True
    db.execute("""INSERT OR IGNORE INTO relationship_evidence(relationship_id,provenance_id,evidence_role,evidence_summary)
       VALUES(?,?,'supporting',?)""",(rid,prid,notes))
    return created


def import_snapshot(db,payload):
    apply_schema(db); migrate_connections(db); harden_connections(db)
    prid,pc=provenance(db,payload['source'])
    stats={'provenance_created':int(pc),'entities_created':0,'entities_existing':0,'points_created':0,'points_existing':0,
           'assertions_created':0,'evidence_created':0,'attestations_created':0,'relationships_created':0}
    by_name={}
    for row in payload['contacts']:
        eid,created=entity(db,row['entity_type'],row['name'],row.get('verification','document_sourced'), source_record_id=row.get('key'))
        by_name[row['name']]=eid
        stats['entities_created' if created else 'entities_existing']+=1
    # ensure referenced parents exist without duplicating existing canonical names
    for row in payload['contacts']:
        if row.get('parent') and row['parent'] not in by_name:
            eid,created=entity(db,'organization',row['parent'])
            by_name[row['parent']]=eid
            stats['entities_created' if created else 'entities_existing']+=1
    for row in payload['contacts']:
        eid=by_name[row['name']]; sp=f"register:{row['key']}:{row.get('source_reference','')}"
        for attr,val in [('register_contact_id',row.get('key')),('role_unit',row.get('role')),('source_reference',row.get('source_reference'))]:
            if attestation(db,eid,prid,attr,val,sp): stats['attestations_created']+=1
        for p in row.get('points',[]):
            pid,created=point(db,p); stats['points_created' if created else 'points_existing']+=1
            aid,created_a=assertion(db,eid,pid,'document_sourced',f"Document-sourced register coordinate; {sp}")
            stats['assertions_created']+=int(created_a)
            stats['evidence_created']+=int(evidence(db,aid,prid,f"{row['key']} {row.get('source_reference','')}"))
        if row.get('parent'):
            rel='works_for' if row['entity_type']=='person' else 'service_unit_of'
            stats['relationships_created']+=int(relation(db,eid,by_name[row['parent']],prid,rel,f"{row.get('role','')}; {sp}"))
    return stats


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--database',default='/var/lib/edge1-phone-intelligence/phone-intelligence.sqlite')
    ap.add_argument('--snapshot',required=True); ap.add_argument('--backup-dir',default='/var/lib/edge1-contacts-maintenance/backups'); ap.add_argument('--commit',action='store_true')
    a=ap.parse_args(); dbp=Path(a.database); payload=json.loads(Path(a.snapshot).read_text()); before=sha256(dbp); backup=None
    if a.commit:
        bd=Path(a.backup_dir); bd.mkdir(parents=True,exist_ok=True); stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        backup=bd/f'phone-intelligence-before-register-import-{stamp}.sqlite'; shutil.copy2(dbp,backup)
        if sha256(backup)!=before: raise RuntimeError('backup hash mismatch')
    db=sqlite3.connect(dbp); db.execute('PRAGMA foreign_keys=ON')
    try:
        db.execute('BEGIN IMMEDIATE' if a.commit else 'BEGIN'); stats=import_snapshot(db,payload)
        integrity=db.execute('PRAGMA integrity_check').fetchone()[0]; fk=db.execute('PRAGMA foreign_key_check').fetchall()
        if integrity!='ok' or fk: raise RuntimeError(f'verification failed integrity={integrity} fk={fk[:5]}')
        db.commit() if a.commit else db.rollback()
    except Exception: db.rollback(); raise
    finally: db.close()
    print(json.dumps({'stats':stats,'transaction':'COMMITTED' if a.commit else 'ROLLED_BACK','backup':str(backup) if backup else None,
                      'source_sha256_before':before,'source_sha256_after':sha256(dbp)},indent=2,sort_keys=True))

if __name__=='__main__': main()
