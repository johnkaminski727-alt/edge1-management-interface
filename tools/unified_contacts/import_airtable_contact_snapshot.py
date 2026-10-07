#!/usr/bin/env python3
"""Import a conservative Airtable contact-registry snapshot into Unified Contacts."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.unified_contacts.schema_contacts_expansion import apply_schema
from tools.unified_contacts.schema_connections import migrate as migrate_connections, harden as harden_connections


def now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def one_or_create_provenance(db, source):
    rows = db.execute('''SELECT id FROM provenance_records
        WHERE source_kind=? AND source_name=? AND COALESCE(source_reference,'')=?
          AND COALESCE(extraction_method,'')=? ORDER BY id''', (
        source['source_kind'], source['source_name'], source.get('source_reference',''),
        source.get('extraction_method',''))).fetchall()
    if len(rows) > 1:
        raise RuntimeError('ambiguous Airtable provenance record')
    if rows:
        return rows[0][0], False
    cur = db.execute('''INSERT INTO provenance_records(
        source_kind,source_name,source_reference,extraction_method,verification_status,notes)
        VALUES(?,?,?,?,?,?)''', (
        source['source_kind'], source['source_name'], source.get('source_reference'),
        source.get('extraction_method'), source.get('verification_status','document_sourced'),
        'Imported from approved Airtable contact-registry snapshot.'))
    return cur.lastrowid, True


def entity(db, entity_type, name):
    rows = db.execute('''SELECT id,entity_type FROM contact_entities
        WHERE lower(canonical_name)=lower(?) ORDER BY id''', (name,)).fetchall()
    if len(rows) > 1:
        raise RuntimeError(f'ambiguous canonical entity: {name}')
    if rows:
        if rows[0][1] != entity_type:
            raise RuntimeError(f'entity type conflict: {name}')
        return rows[0][0], False
    cur = db.execute('''INSERT INTO contact_entities(
        entity_type,canonical_name,display_name,verification_status,lifecycle_status)
        VALUES(?,?,?,'document_sourced','active')''', (entity_type,name,name))
    return cur.lastrowid, True


def attestation(db, provenance_id, entity_id, attribute, value, source_path, classification=None, verification='document_sourced'):
    if value is None or str(value).strip() == '':
        return False
    value = str(value)
    rows = db.execute('''SELECT id FROM contact_attestations
        WHERE entity_id=? AND contact_point_id IS NULL AND provenance_id=?
          AND attribute=? AND attested_value=? AND COALESCE(source_path,'')=? ORDER BY id''',
        (entity_id, provenance_id, attribute, value, source_path)).fetchall()
    if rows:
        return False
    db.execute('''INSERT INTO contact_attestations(
        entity_id,provenance_id,attribute,attested_value,classification,
        verification_status,source_path,notes)
        VALUES(?,?,?,?,?,?,?,?)''', (
        entity_id, provenance_id, attribute, value, classification,
        verification, source_path, 'Imported from Airtable registry snapshot.'))
    return True


def relationship(db, provenance_id, person_id, org_id, status, role, source_path):
    lifecycle = 'inactive' if status == 'Historical' else 'active'
    rows = db.execute('''SELECT id,lifecycle_status FROM contact_relationships
        WHERE left_entity_id=? AND right_entity_id=? AND relationship_type='works_for'
        ORDER BY id''', (person_id,org_id)).fetchall()
    active = [r for r in rows if r[1] == lifecycle]
    if active:
        rid = active[0][0]
        created = False
    elif rows:
        rid = rows[0][0]
        db.execute('''UPDATE contact_relationships SET lifecycle_status=?,updated_at=CURRENT_TIMESTAMP,
            notes=? WHERE id=?''', (lifecycle, f'Airtable role: {role}; source_status={status}', rid))
        created = False
    else:
        cur = db.execute('''INSERT INTO contact_relationships(
            left_entity_id,right_entity_id,relationship_type,confidence,lifecycle_status,directionality,notes)
            VALUES(?,?,'works_for','document_sourced',?,'directed',?)''',
            (person_id,org_id,lifecycle,f'Airtable role: {role}; source_status={status}'))
        rid = cur.lastrowid
        created = True
    db.execute('''INSERT OR IGNORE INTO relationship_evidence(
        relationship_id,provenance_id,evidence_role,evidence_summary)
        VALUES(?,?, 'supporting', ?)''',
        (rid, provenance_id, f'Airtable registry links person to organization; {source_path}'))
    return created


def import_snapshot(db, payload):
    apply_schema(db)
    migrate_connections(db)
    harden_connections(db)
    provenance_id, prov_created = one_or_create_provenance(db, payload['source'])
    stats = {'provenance_created': int(prov_created), 'people_created':0, 'people_existing':0,
             'organizations_created':0, 'organizations_existing':0,'relationships_created':0,
             'attestations_created':0,'do_not_contact':0,'historical':0}
    for row in payload['people']:
        path = f"airtable:{row['source_id']}"
        person_id, created = entity(db,'person',row['name'])
        stats['people_created' if created else 'people_existing'] += 1
        org_id, created_org = entity(db,'organization',row['organization'])
        stats['organizations_created' if created_org else 'organizations_existing'] += 1
        if relationship(db,provenance_id,person_id,org_id,row['status'],row.get('role',''),path):
            stats['relationships_created'] += 1
        fields = [
            ('role_title',row.get('role'),'airtable_role'),
            ('registry_status',row.get('status'),'airtable_status'),
            ('contact_type',row.get('contact_type'),'airtable_contact_type'),
            ('authoritative_contact_source',row.get('authoritative_source'),'source_locator'),
            ('last_verified',row.get('last_verified'),'verification_date'),
            ('source_record_id',row.get('source_id'),'airtable_record_id'),
            ('notes',row.get('notes'),'source_note'),
        ]
        if row.get('status') == 'Do Not Contact':
            fields.append(('communication_policy','do_not_contact','restriction'))
            stats['do_not_contact'] += 1
        if row.get('status') == 'Historical':
            fields.append(('contact_lifecycle','historical','historical_status'))
            stats['historical'] += 1
        for attr,value,classification in fields:
            if attestation(db,provenance_id,person_id,attr,value,path,classification):
                stats['attestations_created'] += 1
    return stats


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--database',default='/var/lib/edge1-phone-intelligence/phone-intelligence.sqlite')
    ap.add_argument('--snapshot',required=True)
    ap.add_argument('--backup-dir',default='/var/lib/edge1-contacts-maintenance/backups')
    ap.add_argument('--commit',action='store_true')
    args=ap.parse_args()
    db_path=Path(args.database); snapshot=Path(args.snapshot)
    payload=json.loads(snapshot.read_text())
    before=sha256(db_path)
    backup=None
    if args.commit:
        out=Path(args.backup_dir); out.mkdir(parents=True,exist_ok=True)
        stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        backup=out/f'phone-intelligence-before-airtable-import-{stamp}.sqlite'
        shutil.copy2(db_path,backup)
        if sha256(backup)!=before:
            raise RuntimeError('backup hash verification failed')
    db=sqlite3.connect(db_path); db.execute('PRAGMA foreign_keys=ON')
    try:
        db.execute('BEGIN IMMEDIATE' if args.commit else 'BEGIN')
        stats=import_snapshot(db,payload)
        integrity=db.execute('PRAGMA integrity_check').fetchone()[0]
        fk=db.execute('PRAGMA foreign_key_check').fetchall()
        if integrity!='ok' or fk:
            raise RuntimeError(f'database verification failed integrity={integrity} fk={fk[:5]}')
        if args.commit: db.commit()
        else: db.rollback()
    except Exception:
        db.rollback(); raise
    finally:
        db.close()
    result={'stats':stats,'transaction':'COMMITTED' if args.commit else 'ROLLED_BACK',
            'source_sha256_before':before,'source_sha256_after':sha256(db_path),
            'backup':str(backup) if backup else None,'completed_at':now()}
    print(json.dumps(result,indent=2,sort_keys=True))

if __name__=='__main__': main()
