#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, sqlite3
from datetime import datetime, timezone
from pathlib import Path

CATALOG=Path('/var/lib/bigbird-ai-library/catalog/source-catalog.sqlite3')
BRIDGE=Path('/var/lib/edge1-evidence-intake/provider-bridge')

def now(): return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
def iid(source_id, external_id): return hashlib.sha256(f'{source_id}\0{external_id}'.encode()).hexdigest()

def snapshot_path(source_id): return BRIDGE/source_id/'snapshot.json'

def poll_one(db, source):
    started=now(); sid=source['id']
    cur=db.execute("INSERT INTO library_sync_runs(source_id,started_at,status) VALUES(?,?,?)",(sid,started,'running'))
    run_id=cur.lastrowid
    stats={'scanned':0,'new_items':0,'changed_items':0,'preserved':0,'indexed':0,'deferred':0,'errors':0}
    detail={}
    try:
        if not source['enabled']:
            status='disabled'; detail={'reason':'source_disabled'}
        elif source['runtime_access']=='local':
            status='available'; detail={'reason':'local_source_reconciled_by_catalog'}
        else:
            path=snapshot_path(sid)
            if not path.is_file():
                status='deferred'; stats['deferred']=1; detail={'reason':'connector_bridge_snapshot_missing','expected_path':str(path)}
            else:
                payload=json.loads(path.read_text())
                if payload.get('source_id') != sid or not isinstance(payload.get('items'),list):
                    raise ValueError('invalid bridge snapshot contract')
                seen=set()
                for item in payload['items']:
                    ext=str(item.get('external_id') or '').strip()
                    title=str(item.get('title') or '').strip()
                    if not ext or not title: continue
                    seen.add(ext); stats['scanned']+=1
                    old=db.execute('SELECT id,provider_modified_at,revision_id,content_sha256,title FROM library_items WHERE source_id=? AND external_id=?',(sid,ext)).fetchone()
                    new_id=iid(sid,ext)
                    changed=bool(old and (old['provider_modified_at']!=item.get('provider_modified_at') or old['revision_id']!=item.get('revision_id') or old['content_sha256']!=item.get('content_sha256') or old['title']!=title))
                    if old is None: stats['new_items']+=1
                    elif changed: stats['changed_items']+=1
                    db.execute('''INSERT INTO library_items(id,source_id,external_id,parent_external_id,item_type,title,original_name,source_url,source_path,mime_type,size_bytes,provider_created_at,provider_modified_at,revision_id,content_sha256,local_path,evidence_source_document_id,library_document_id,copy_state,sync_state,first_seen_at,last_seen_at,indexed_at)
                      VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                      ON CONFLICT(source_id,external_id) DO UPDATE SET parent_external_id=excluded.parent_external_id,item_type=excluded.item_type,title=excluded.title,original_name=excluded.original_name,source_url=excluded.source_url,source_path=excluded.source_path,mime_type=excluded.mime_type,size_bytes=excluded.size_bytes,provider_created_at=excluded.provider_created_at,provider_modified_at=excluded.provider_modified_at,revision_id=excluded.revision_id,content_sha256=COALESCE(excluded.content_sha256,library_items.content_sha256),local_path=COALESCE(excluded.local_path,library_items.local_path),copy_state=CASE WHEN library_items.copy_state IN('preserved','cached') THEN library_items.copy_state ELSE excluded.copy_state END,sync_state=excluded.sync_state,last_seen_at=excluded.last_seen_at''',
                      (new_id,sid,ext,item.get('parent_external_id'),item.get('item_type','document'),title,item.get('original_name'),item.get('source_url'),item.get('source_path'),item.get('mime_type'),item.get('size_bytes'),item.get('provider_created_at'),item.get('provider_modified_at'),item.get('revision_id'),item.get('content_sha256'),item.get('local_path'),item.get('evidence_source_document_id'),item.get('library_document_id'),item.get('copy_state','reference'),'changed' if changed else ('new' if old is None else 'current'),started,started,item.get('indexed_at')))
                    stored=db.execute('SELECT id FROM library_items WHERE source_id=? AND external_id=?',(sid,ext)).fetchone()
                    if not stored: raise RuntimeError('provider item upsert did not resolve stored id')
                    stored_id=stored['id']
                    for domain in ('contacts','accounting','filing'):
                        db.execute('INSERT OR IGNORE INTO library_item_domain_state(item_id,domain,state) VALUES(?,?,?)',(stored_id,domain,'pending'))
                    for k,v in (item.get('metadata') or {}).items():
                        db.execute('INSERT OR REPLACE INTO library_item_metadata(item_id,key,value_json,provenance,updated_at) VALUES(?,?,?,?,?)',(stored_id,str(k),json.dumps(v,sort_keys=True),'provider-bridge',started))
                if payload.get('complete',False):
                    rows=db.execute('SELECT external_id FROM library_items WHERE source_id=?',(sid,)).fetchall()
                    for r in rows:
                        if r['external_id'] not in seen and not str(r['external_id']).startswith('source_document:'):
                            db.execute("UPDATE library_items SET sync_state='deleted_remote',last_seen_at=? WHERE source_id=? AND external_id=?",(started,sid,r['external_id']))
                status='succeeded'; detail={'snapshot_generated_at':payload.get('generated_at'),'complete':bool(payload.get('complete',False)),'snapshot_path':str(path)}
        db.execute('UPDATE library_sources SET last_sync_at=?,last_status=?,last_error=NULL,updated_at=? WHERE id=?',(started,status,started,sid))
    except Exception as exc:
        status='failed'; stats['errors']=1; detail={'error':str(exc)}
        db.execute('UPDATE library_sources SET last_sync_at=?,last_status=?,last_error=?,updated_at=? WHERE id=?',(started,status,str(exc)[:2000],started,sid))
    finished=now()
    db.execute('''UPDATE library_sync_runs SET finished_at=?,status=?,scanned=?,new_items=?,changed_items=?,preserved=?,indexed=?,deferred=?,errors=?,detail_json=? WHERE id=?''',
      (finished,status,stats['scanned'],stats['new_items'],stats['changed_items'],stats['preserved'],stats['indexed'],stats['deferred'],stats['errors'],json.dumps(detail,sort_keys=True),run_id))
    return {'source_id':sid,'status':status,**stats,'detail':detail}

def submit_workflow_if_changed(out, generated, inbox=Path('/var/lib/wwcx-ava-office-manager/workflow-inbox')):
    changed=sum(int(x.get('new_items') or 0)+int(x.get('changed_items') or 0) for x in out)
    if changed<=0 or any(x.get('status')=='failed' for x in out): return None
    inbox.mkdir(parents=True,exist_ok=True)
    trigger_ref='library-provider-delta:'+hashlib.sha256(json.dumps([(x['source_id'],x.get('new_items',0),x.get('changed_items',0),x.get('detail',{}).get('snapshot_generated_at')) for x in out],sort_keys=True).encode()).hexdigest()
    request={'workflow_id':'provider-evidence-processing','trigger_type':'library-provider-change','trigger_ref':trigger_ref,'requested_by':'edge1-library-provider-poll','priority':'normal','detail':{'changed_items':changed,'generated_at':generated}}
    target=inbox/(hashlib.sha256(trigger_ref.encode()).hexdigest()+'.json')
    if not target.exists() and not target.with_suffix('.processed').exists():
        target.write_text(json.dumps(request,indent=2,sort_keys=True)+'\n'); os.chmod(target,0o640)
    return target

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--source'); ap.add_argument('--all',action='store_true'); ap.add_argument('--db',default=str(CATALOG)); a=ap.parse_args()
    if not a.source and not a.all: ap.error('use --source ID or --all')
    with sqlite3.connect(a.db) as db:
        db.row_factory=sqlite3.Row; db.execute('PRAGMA foreign_keys=ON')
        if a.source:
            rows=db.execute('SELECT * FROM library_sources WHERE id=?',(a.source,)).fetchall()
            if not rows: raise SystemExit('unknown source')
        else: rows=db.execute('SELECT * FROM library_sources ORDER BY provider,name').fetchall()
        out=[poll_one(db,r) for r in rows]; db.commit()
    generated=now()
    payload={'contract':'edge1.library-provider-poll.v1','generated_at':generated,'results':out}
    submit_workflow_if_changed(out,generated)
    print(json.dumps(payload,sort_keys=True))
    return 1 if any(x['status']=='failed' for x in out) else 0
if __name__=='__main__': raise SystemExit(main())
