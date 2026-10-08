#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, sqlite3, sys, urllib.error, urllib.request, uuid
from pathlib import Path
from typing import Any
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from server.ava_office_manager import OfficeManagerStore, utc_now

DB=Path('/var/lib/wwcx-ava-office-manager/office-manager.sqlite3')
REGISTRY=ROOT/'config/ava-executive-capabilities.json'
INBOX=Path('/var/lib/wwcx-ava-office-manager/workflow-inbox')
STATUS=Path('/var/www/edge1-status/ava/workflow-status.json')
ALLOWED_HOSTS={'127.0.0.1','localhost'}
TERMINAL={'completed','failed','cancelled','blocked'}

class DispatchError(RuntimeError): pass

def _id(prefix:str)->str: return f'{prefix}-{uuid.uuid4().hex}'
def load_registry(path:Path=REGISTRY)->dict[str,Any]:
    data=json.loads(path.read_text())
    if data.get('contract')!='wwcx.ava-executive-capabilities.v1': raise DispatchError('unsupported capability registry')
    caps={}
    for c in data.get('capabilities',[]):
        cid=str(c.get('id') or '')
        if not cid or cid in caps: raise DispatchError('invalid or duplicate capability')
        if c.get('transport')!='http_json': raise DispatchError(f'unsupported transport for {cid}')
        from urllib.parse import urlparse
        u=urlparse(str(c.get('endpoint') or ''))
        if u.scheme!='http' or u.hostname not in ALLOWED_HOSTS: raise DispatchError(f'non-loopback endpoint for {cid}')
        if c.get('authority') not in {'observe','prepare','routine'}: raise DispatchError(f'unsafe authority for {cid}')
        if c.get('autonomous') is not True: raise DispatchError(f'capability not autonomous: {cid}')
        caps[cid]=c
    flows={str(w['id']):w for w in data.get('workflows',[]) if w.get('autonomous') is True}
    return {'raw':data,'caps':caps,'flows':flows}

def invoke(cap:dict[str,Any], timeout:int)->dict[str,Any]:
    body=json.dumps(cap.get('body') or {},sort_keys=True).encode()
    req=urllib.request.Request(str(cap['endpoint']),data=body,method=str(cap.get('method') or 'POST'))
    for k,v in (cap.get('headers') or {}).items(): req.add_header(str(k),str(v))
    try:
        with urllib.request.urlopen(req,timeout=timeout) as r:
            raw=r.read(1024*1024); status=r.status
    except urllib.error.HTTPError as e:
        raw=e.read(256*1024); status=e.code
    text=raw.decode('utf-8','replace')
    try: payload=json.loads(text) if text else {}
    except Exception: payload={'raw':text[-8000:]}
    ok=status in set(int(x) for x in cap.get('success_statuses',[200]))
    return {'ok':ok,'http_status':status,'response':payload}

def ensure_workflow_schema(store:OfficeManagerStore)->None:
    # OfficeManagerStore initialization performs migrations.
    with store.connect() as c:
        c.execute('SELECT 1 FROM executive_workflow_runs LIMIT 1')

def create_run(store:OfficeManagerStore, reg:dict[str,Any], request:dict[str,Any])->tuple[str,bool]:
    wid=str(request.get('workflow_id') or '')
    if wid not in reg['flows']: raise DispatchError('unknown or non-autonomous workflow')
    trigger_ref=str(request.get('trigger_ref') or '').strip()
    if not trigger_ref or len(trigger_ref)>1024: raise DispatchError('invalid trigger_ref')
    trigger_type=str(request.get('trigger_type') or reg['flows'][wid].get('trigger') or 'manual')[:128]
    requested_by=str(request.get('requested_by') or 'ava-executive')[:128]
    flow=reg['flows'][wid]; now=utc_now()
    with store.connect() as c:
        old=c.execute('SELECT id FROM executive_workflow_runs WHERE workflow_id=? AND trigger_ref=?',(wid,trigger_ref)).fetchone()
        if old: return str(old['id']),False
    existing_work_id=str(request.get('work_item_id') or '').strip()
    if existing_work_id:
        work=store.get_work_item(existing_work_id)
    else:
        objective=str(request.get('objective') or '').strip()[:1000]
        work=store.create_work_item(title='AVA workflow: '+str(flow.get('name') or wid),desired_outcome=objective or str(flow.get('description') or 'Complete the registered autonomous workflow.'),source_channel='ava-workflow',source_ref='workflow:'+wid+':'+hashlib.sha256(trigger_ref.encode()).hexdigest()[:24],priority=str(request.get('priority') or 'normal'),owner='ava',actor='ava-dispatcher')
    run_id=_id('workflow');
    with store.connect() as c:
        c.execute('INSERT INTO executive_workflow_runs(id,workflow_id,trigger_type,trigger_ref,state,requested_by,work_item_id,created_at_utc,updated_at_utc) VALUES(?,?,?,?,?,?,?,?,?)',(run_id,wid,trigger_type,trigger_ref,'queued',requested_by,work['id'],now,now))
        for step in flow.get('steps',[]):
            cap_id=str(step.get('capability') or ''); cap=reg['caps'].get(cap_id)
            if not cap: raise DispatchError(f'workflow references unavailable capability {cap_id}')
            c.execute('INSERT INTO executive_workflow_steps(id,run_id,step_key,capability,member_id,state,depends_on_json,created_at_utc,updated_at_utc) VALUES(?,?,?,?,?,?,?,?,?)',(_id('step'),run_id,str(step['id']),cap_id,str(cap['team_member']),'pending',json.dumps(step.get('depends_on') or [],sort_keys=True),now,now))
    store._audit('ava-dispatcher','workflow.created','workflow_run',run_id,{'workflow_id':wid,'trigger_type':trigger_type,'work_item_id':work['id']})
    return run_id,True

def process_inbox(store:OfficeManagerStore, reg:dict[str,Any])->int:
    INBOX.mkdir(parents=True,exist_ok=True); count=0
    for p in sorted(INBOX.glob('*.json'))[:200]:
        try:
            req=json.loads(p.read_text()); create_run(store,reg,req)
            p.rename(p.with_suffix('.processed')); count+=1
        except Exception as exc:
            try: p.rename(p.with_suffix('.error'))
            except OSError: pass
            store._audit('ava-dispatcher','workflow.request.rejected','workflow_request',hashlib.sha256(str(p).encode()).hexdigest()[:32],{'error':str(exc)[:500]})
    return count

def dependencies_done(c:sqlite3.Connection, run_id:str, deps:list[str])->bool:
    if not deps: return True
    rows=c.execute('SELECT step_key,state FROM executive_workflow_steps WHERE run_id=?',(run_id,)).fetchall(); states={r['step_key']:r['state'] for r in rows}
    return all(states.get(d)=='completed' for d in deps)

def dispatch_ready(store:OfficeManagerStore, reg:dict[str,Any], max_steps:int=25)->dict[str,int]:
    started=completed=failed=blocked=retried=0; default_timeout=int(reg['raw'].get('default_timeout_seconds') or 180); default_max_attempts=max(1,int(reg['raw'].get('default_max_attempts') or 2))
    with store.connect() as c: runs=[dict(r) for r in c.execute("SELECT * FROM executive_workflow_runs WHERE state IN ('queued','running') ORDER BY created_at_utc LIMIT 50")]
    for run in runs:
        with store.connect() as c:
            steps=[dict(r) for r in c.execute('SELECT * FROM executive_workflow_steps WHERE run_id=? ORDER BY created_at_utc,step_key',(run['id'],))]
        if any(s['state']=='failed' for s in steps):
            with store.connect() as c:c.execute("UPDATE executive_workflow_runs SET state='failed',updated_at_utc=?,completed_at_utc=?,error_summary=? WHERE id=?",(utc_now(),utc_now(),'one or more workflow steps failed',run['id']))
            continue
        progressed=True
        while progressed and started<max_steps:
            progressed=False
            with store.connect() as c:
                steps=[dict(r) for r in c.execute('SELECT * FROM executive_workflow_steps WHERE run_id=? ORDER BY created_at_utc,step_key',(run['id'],))]
                for step in steps:
                    if step['state']!='pending': continue
                    deps=json.loads(step['depends_on_json'])
                    if not dependencies_done(c,run['id'],deps): continue
                    cap=reg['caps'].get(step['capability'])
                    if not cap:
                        c.execute("UPDATE executive_workflow_steps SET state='blocked',error_summary=?,updated_at_utc=? WHERE id=?",('capability missing from registry',utc_now(),step['id'])); blocked+=1; progressed=True; continue
                    member=c.execute('SELECT authority_ceiling,active FROM executive_team_members WHERE member_id=?',(cap['team_member'],)).fetchone()
                    order={'observe':1,'prepare':2,'routine':3}
                    if not member or not member['active'] or order.get(str(cap['authority']),99)>order.get(str(member['authority_ceiling']),0):
                        c.execute("UPDATE executive_workflow_steps SET state='blocked',error_summary=?,updated_at_utc=? WHERE id=?",('team member authority does not cover capability',utc_now(),step['id'])); blocked+=1; progressed=True; continue
                    now=utc_now(); c.execute("UPDATE executive_workflow_steps SET state='running',attempt_count=attempt_count+1,started_at_utc=?,updated_at_utc=? WHERE id=?",(now,now,step['id'])); c.execute("UPDATE executive_workflow_runs SET state='running',updated_at_utc=? WHERE id=?",(now,run['id']))
                    started+=1; progressed=True
                    break
            if not progressed or started>max_steps: break
            # Execute outside the DB transaction.
            with store.connect() as c: running=c.execute("SELECT * FROM executive_workflow_steps WHERE run_id=? AND state='running' ORDER BY started_at_utc LIMIT 1",(run['id'],)).fetchone()
            if not running: continue
            cap=reg['caps'][str(running['capability'])]
            result=invoke(cap,int(cap.get('timeout_seconds') or default_timeout)); now=utc_now()
            with store.connect() as c:
                if result['ok']:
                    c.execute("UPDATE executive_workflow_steps SET state='completed',finished_at_utc=?,result_json=?,updated_at_utc=? WHERE id=?",(now,json.dumps(result,sort_keys=True),now,running['id'])); completed+=1
                else:
                    attempts=int(running['attempt_count'])
                    max_attempts=max(1,int(cap.get('max_attempts') or default_max_attempts))
                    if attempts < max_attempts:
                        c.execute("UPDATE executive_workflow_steps SET state='pending',finished_at_utc=?,result_json=?,error_summary=?,updated_at_utc=? WHERE id=?",(now,json.dumps(result,sort_keys=True),f'bounded capability failed; retry {attempts}/{max_attempts} scheduled',now,running['id'])); retried+=1
                    else:
                        c.execute("UPDATE executive_workflow_steps SET state='failed',finished_at_utc=?,result_json=?,error_summary=?,updated_at_utc=? WHERE id=?",(now,json.dumps(result,sort_keys=True),f'bounded capability failed after {attempts} attempts',now,running['id'])); failed+=1
            event='completed' if result['ok'] else ('retry_scheduled' if int(running['attempt_count']) < max(1,int(cap.get('max_attempts') or default_max_attempts)) else 'failed')
            store._audit('ava-dispatcher','workflow.step.'+event,'workflow_step',str(running['id']),{'run_id':run['id'],'capability':running['capability'],'member_id':running['member_id'],'http_status':result['http_status']})
            if not result['ok']: break
        with store.connect() as c:
            states=[str(r['state']) for r in c.execute('SELECT state FROM executive_workflow_steps WHERE run_id=?',(run['id'],))]
            if states and all(s=='completed' for s in states):
                now=utc_now(); c.execute("UPDATE executive_workflow_runs SET state='completed',updated_at_utc=?,completed_at_utc=? WHERE id=?",(now,now,run['id']))
                work_id=run.get('work_item_id'); work_outcome='await_checkin' if run.get('trigger_type')=='team-attention' else 'completed'
            elif any(s in {'failed','blocked'} for s in states):
                now=utc_now(); c.execute("UPDATE executive_workflow_runs SET state='failed',updated_at_utc=?,completed_at_utc=?,error_summary=? WHERE id=?",(now,now,'workflow paused after failed or blocked step',run['id'])); work_id=run.get('work_item_id'); work_outcome='needs_owner'
            else: work_id=None; work_outcome=None
        if work_id:
            try:
                item=store.get_work_item(str(work_id))
                if work_outcome=='completed':
                    if item['state']=='new': store.transition_work_item(str(work_id),'working',actor='ava-dispatcher',note='Autonomous workflow dispatched.')
                    if store.get_work_item(str(work_id))['state']!='completed': store.transition_work_item(str(work_id),'completed',actor='ava-dispatcher',note='All registered workflow steps completed successfully.')
                elif work_outcome=='await_checkin' and item['state'] not in {'completed','cancelled','waiting_external'}:
                    if item['state']=='new': store.transition_work_item(str(work_id),'working',actor='ava-dispatcher',note='Bounded remediation workflow dispatched.')
                    if store.get_work_item(str(work_id))['state']=='working': store.transition_work_item(str(work_id),'waiting_external',actor='ava-dispatcher',note='Remediation completed; waiting for a fresh team health check-in.')
                elif work_outcome=='needs_owner' and item['state'] not in {'completed','cancelled','needs_owner'}:
                    store.transition_work_item(str(work_id),'needs_owner',actor='ava-dispatcher',note='Registered workflow exhausted retries or hit a policy/authority block.')
            except Exception: pass
    return {'steps_started':started,'steps_completed':completed,'steps_failed':failed,'steps_blocked':blocked,'steps_retry_scheduled':retried}

def reconcile_legacy_work_links(store:OfficeManagerStore)->int:
    changed=0
    with store.connect() as c:
        runs=[dict(r) for r in c.execute("SELECT id,trigger_type,trigger_ref,state,work_item_id FROM executive_workflow_runs WHERE trigger_type IN ('team-attention','acceptance')")]
    for run in runs:
        current_id=str(run.get('work_item_id') or '')
        if run['trigger_type']=='acceptance' and run['state']=='failed' and current_id:
            try:
                item=store.get_work_item(current_id)
                if item['state'] in {'new','working','waiting_external','needs_owner','scheduled'}:
                    store.transition_work_item(current_id,'cancelled',actor='ava-dispatcher-migration',note='Acceptance/calibration workflow retained as history; superseded open work closed.')
                    changed+=1
            except Exception: pass
            continue
        if run['trigger_type']!='team-attention': continue
        parts=str(run['trigger_ref']).split(':')
        canonical=parts[-1] if parts and parts[-1].startswith('work-') else ''
        if not canonical or canonical==current_id: continue
        try: canonical_item=store.get_work_item(canonical)
        except Exception: continue
        with store.connect() as c: c.execute('UPDATE executive_workflow_runs SET work_item_id=?,updated_at_utc=? WHERE id=?',(canonical,utc_now(),run['id']))
        if run['state']=='failed' and canonical_item['state'] not in {'completed','cancelled','needs_owner'}:
            try: store.transition_work_item(canonical,'needs_owner',actor='ava-dispatcher-migration',note='Historical bounded remediation exhausted retries; canonical attention item retained.')
            except Exception: pass
        elif run['state']=='completed' and canonical_item['state'] not in {'completed','cancelled','waiting_external'}:
            try:
                if canonical_item['state']=='new': store.transition_work_item(canonical,'working',actor='ava-dispatcher-migration',note='Historical remediation completed.')
                if store.get_work_item(canonical)['state']=='working': store.transition_work_item(canonical,'waiting_external',actor='ava-dispatcher-migration',note='Waiting for fresh bot health verification.')
            except Exception: pass
        if current_id:
            try:
                duplicate=store.get_work_item(current_id)
                if duplicate['state'] in {'new','working','waiting_external','needs_owner','scheduled'}:
                    store.transition_work_item(current_id,'cancelled',actor='ava-dispatcher-migration',note='Superseded duplicate workflow work item; canonical attention item retained.')
            except Exception: pass
        store._audit('ava-dispatcher-migration','workflow.work.relinked','workflow_run',str(run['id']),{'canonical_work_item_id':canonical,'superseded_work_item_id':current_id})
        changed+=1
    return changed

def status(store:OfficeManagerStore, processed:int, stats:dict[str,int])->dict[str,Any]:
    with store.connect() as c:
        runs={r['state']:r['c'] for r in c.execute('SELECT state,count(*) c FROM executive_workflow_runs GROUP BY state')}
        steps={r['state']:r['c'] for r in c.execute('SELECT state,count(*) c FROM executive_workflow_steps GROUP BY state')}
        recent=[dict(r) for r in c.execute('SELECT id,workflow_id,trigger_type,state,created_at_utc,updated_at_utc,completed_at_utc,error_summary FROM executive_workflow_runs ORDER BY created_at_utc DESC LIMIT 20')]
    out={'contract':'wwcx.ava-workflow-dispatcher.v1','generated_at':utc_now(),'requests_processed':processed,'runs':runs,'steps':steps,'recent_runs':recent,**stats,'generic_shell_enabled':False,'registered_capabilities_only':True}
    STATUS.parent.mkdir(parents=True,exist_ok=True); STATUS.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n'); os.chmod(STATUS,0o644); return out

def run(db:Path=DB, registry:Path=REGISTRY)->dict[str,Any]:
    store=OfficeManagerStore(db); ensure_workflow_schema(store); migrated=reconcile_legacy_work_links(store); reg=load_registry(registry); processed=process_inbox(store,reg); stats=dispatch_ready(store,reg); stats['legacy_work_links_reconciled']=migrated; return status(store,processed,stats)

def main()->int:
    a=argparse.ArgumentParser(); a.add_argument('--db',type=Path,default=DB); a.add_argument('--registry',type=Path,default=REGISTRY); x=a.parse_args(); print(json.dumps(run(x.db,x.registry),sort_keys=True)); return 0
if __name__=='__main__': raise SystemExit(main())
