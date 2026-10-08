#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json,shutil,sqlite3,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2] if 'tools/unified_contacts' in str(Path(__file__).resolve()) else Path('/opt/edge1-management-interface')
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from tools.unified_contacts.schema_contacts_expansion import apply_schema
from tools.unified_contacts.schema_connections import migrate as migrate_connections,harden as harden_connections
from tools.unified_contacts.identity_gate import require_safe_entity_resolution

def sha256(p):
 h=hashlib.sha256();
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
 return h.hexdigest()

def provenance(db,source):
 sd=source.get('source_document_id')
 rows=db.execute("SELECT id FROM provenance_records WHERE source_kind=? AND source_name=? AND COALESCE(source_reference,'')=? AND COALESCE(extraction_method,'')=? AND COALESCE(source_document_id,0)=COALESCE(?,0) ORDER BY id",(source['source_kind'],source['source_name'],source.get('source_reference',''),source.get('extraction_method',''),sd)).fetchall()
 if len(rows)>1: raise RuntimeError('ambiguous Airtable organization provenance')
 if rows:return rows[0][0],False
 cur=db.execute("INSERT INTO provenance_records(source_document_id,source_kind,source_name,source_reference,extraction_method,verification_status,notes) VALUES(?,?,?,?,?,?,?)",(sd,source['source_kind'],source['source_name'],source.get('source_reference'),source.get('extraction_method'),source.get('verification_status','document_sourced'),'Imported from approved Airtable organization registry snapshot.'))
 return cur.lastrowid,True

def attest(db,eid,pid,attr,val,path,classification):
 if val is None or str(val).strip()=='': return False
 val=str(val)
 row=db.execute("SELECT id FROM contact_attestations WHERE entity_id=? AND contact_point_id IS NULL AND provenance_id=? AND attribute=? AND attested_value=? AND COALESCE(source_path,'')=?",(eid,pid,attr,val,path)).fetchone()
 if row:return False
 db.execute("INSERT INTO contact_attestations(entity_id,provenance_id,attribute,attested_value,classification,verification_status,source_path,notes) VALUES(?,?,?,?,?,'document_sourced',?,?)",(eid,pid,attr,val,classification,path,'Imported from Airtable organization registry snapshot.'))
 return True

def import_snapshot(db,payload):
 apply_schema(db);migrate_connections(db);harden_connections(db)
 pid,pc=provenance(db,payload['source'])
 stats={'provenance_created':int(pc),'organizations_created':0,'organizations_existing':0,'attestations_created':0,'skipped_unverified':0,'skipped_archived':0}
 for r in payload['organizations']:
  status=str(r.get('status') or '')
  conf=str(r.get('confidence') or '')
  if status!='Active': stats['skipped_archived']+=1; continue
  if conf not in {'High','Verified'}: stats['skipped_unverified']+=1; continue
  name=str(r.get('name') or '').strip()
  if not name: continue
  eid,create,match=require_safe_entity_resolution(db,'organization',name,source_record_id=r.get('source_id'))
  if create:
   cur=db.execute("INSERT INTO contact_entities(entity_type,canonical_name,display_name,verification_status,lifecycle_status) VALUES('organization',?,?,'document_sourced','active')",(name,name));eid=cur.lastrowid;stats['organizations_created']+=1
  else: stats['organizations_existing']+=1
  path='airtable:'+r['source_id']
  fields=[('source_record_id',r.get('source_id'),'airtable_record_id'),('organization_type',r.get('organization_type'),'airtable_type'),('registry_status',status,'airtable_status'),('website',r.get('website'),'source_locator'),('authoritative_record_location',r.get('authoritative_record_location'),'source_locator'),('last_verified',r.get('last_verified'),'verification_date'),('confidence',conf,'verification_confidence'),('sensitivity',r.get('sensitivity'),'handling_classification'),('notes',r.get('notes'),'source_note')]
  for a,v,c in fields: stats['attestations_created']+=int(attest(db,eid,pid,a,v,path,c))
 return stats

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--database',default='/var/lib/edge1-phone-intelligence/phone-intelligence.sqlite');ap.add_argument('--snapshot',required=True);ap.add_argument('--source-document-id',type=int);ap.add_argument('--backup-dir',default='/var/lib/edge1-contacts-maintenance/backups');ap.add_argument('--commit',action='store_true');a=ap.parse_args()
 dbp=Path(a.database); before=sha256(dbp); backup=None; payload=json.load(open(a.snapshot))
 if a.source_document_id is not None:
  if a.source_document_id < 1: raise SystemExit('--source-document-id must be positive')
  payload=dict(payload); payload['source']=dict(payload['source']); payload['source']['source_document_id']=a.source_document_id
 if a.commit:
  bd=Path(a.backup_dir);bd.mkdir(parents=True,exist_ok=True);backup=bd/f"phone-intelligence-before-airtable-org-import-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.sqlite";shutil.copy2(dbp,backup)
  if sha256(backup)!=before: raise RuntimeError('backup hash mismatch')
 db=sqlite3.connect(dbp);db.execute('PRAGMA foreign_keys=ON')
 try:
  db.execute('BEGIN IMMEDIATE' if a.commit else 'BEGIN');stats=import_snapshot(db,payload);integ=db.execute('PRAGMA integrity_check').fetchone()[0];fk=db.execute('PRAGMA foreign_key_check').fetchall();
  if integ!='ok' or fk: raise RuntimeError(f'integrity={integ} fk={fk[:5]}')
  db.commit() if a.commit else db.rollback()
 except Exception: db.rollback();raise
 finally: db.close()
 print(json.dumps({'stats':stats,'transaction':'COMMITTED' if a.commit else 'ROLLED_BACK','backup':str(backup) if backup else None,'source_sha256_before':before,'source_sha256_after':sha256(dbp)},indent=2,sort_keys=True))
if __name__=='__main__':main()
