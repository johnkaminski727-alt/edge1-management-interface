#!/usr/bin/env python3
from __future__ import annotations
import json, subprocess, time
from pathlib import Path
from datetime import datetime, timezone
STATE=Path('/var/lib/edge1-service-self-heal/state.json'); STATUS=Path('/var/www/edge1-status/service-self-heal/status.json')
ALLOW=('edge1-private-library-search.service','edge1-operator-mcp.service','edge1-operations-api.service','private-ai-browser-worker.service','wwcx-mail-room.service','bigbird-ai-gateway.service')
COOLDOWN=3600
TRANSIENT_MIN_AGE_SECONDS=900
TRANSIENT_MAX_PER_RUN=25

def show(unit):
    q=subprocess.run(['systemctl','show',unit,'-p','ActiveState','-p','UnitFileState','-p','Result','-p','Transient','-p','FragmentPath','-p','StateChangeTimestamp'],text=True,capture_output=True,check=False); d={}
    for line in q.stdout.splitlines():
        if '=' in line:k,v=line.split('=',1);d[k]=v
    return d

def load_state():
    try:return json.loads(STATE.read_text())
    except Exception:return {'attempts':{}}

def should_repair(props,last_attempt,now): return props.get('ActiveState')=='failed' and props.get('UnitFileState') in {'enabled','enabled-runtime'} and (not last_attempt or now-last_attempt>=COOLDOWN)

def parse_systemd_time(value):
    if not value:return None
    text=str(value).strip()
    for fmt in ('%a %Y-%m-%d %H:%M:%S %Z','%a %Y-%m-%d %H:%M:%S %z'):
        try:
            parsed=datetime.strptime(text,fmt)
            if parsed.tzinfo is None: parsed=parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError: pass
    return None

def transient_cleanup_candidate(props,now_dt):
    changed=parse_systemd_time(props.get('StateChangeTimestamp'))
    age=None if changed is None else max(0,(now_dt-changed).total_seconds())
    eligible=(props.get('ActiveState')=='failed' and props.get('Transient')=='yes' and props.get('UnitFileState')=='transient' and str(props.get('FragmentPath') or '').startswith('/run/systemd/transient/') and age is not None and age>=TRANSIENT_MIN_AGE_SECONDS)
    return eligible,age

def failed_units():
    q=subprocess.run(['systemctl','list-units','--failed','--no-legend','--no-pager','--plain'],text=True,capture_output=True,check=False)
    out=[]
    for line in q.stdout.splitlines():
        parts=line.split()
        if parts and parts[0].endswith(('.service','.timer','.path','.socket','.mount','.target')): out.append(parts[0])
    return out

def cleanup_transient_failures(now_dt):
    rows=[]; cleared=0
    for unit in failed_units()[:100]:
        props=show(unit); eligible,age=transient_cleanup_candidate(props,now_dt)
        if not eligible: continue
        if len(rows)>=TRANSIENT_MAX_PER_RUN: break
        q=subprocess.run(['systemctl','reset-failed',unit],text=True,capture_output=True,check=False)
        after=show(unit); still_failed=after.get('ActiveState')=='failed'
        ok=q.returncode==0 and not still_failed
        if ok: cleared+=1
        rows.append({'unit':unit,'age_seconds':None if age is None else int(age),'action':'reset_failed' if ok else 'reset_failed_failed','returncode':q.returncode,'after':after.get('ActiveState','not-loaded')})
    return rows,cleared

def main():
    now=time.time(); now_dt=datetime.now(timezone.utc); state=load_state(); attempts=state.setdefault('attempts',{}); rows=[]; repaired=0
    for unit in ALLOW:
        before=show(unit); last=float((attempts.get(unit) or {}).get('at',0) or 0); action='none'; after=before
        if should_repair(before,last,now):
            action='restart_attempted'; attempts[unit]={'at':now,'before':before.get('ActiveState')}; q=subprocess.run(['systemctl','restart',unit],text=True,capture_output=True,check=False,timeout=90); after=show(unit)
            if q.returncode==0 and after.get('ActiveState')=='active': action='restarted_verified'; repaired+=1
            else: action='restart_failed'
            attempts[unit]['result']=action
        rows.append({'unit':unit,'before':before.get('ActiveState','unknown'),'enabled':before.get('UnitFileState','unknown'),'action':action,'after':after.get('ActiveState','unknown'),'cooldown_seconds':COOLDOWN})
    transient_rows,cleared=cleanup_transient_failures(now_dt)
    STATE.parent.mkdir(parents=True,exist_ok=True); STATE.write_text(json.dumps(state,indent=2)+'\n'); STATE.chmod(0o600)
    failed_now=sum(r['after']=='failed' for r in rows)
    out={'contract':'wwcx.service-self-heal.v2','generated_at':now_dt.isoformat(),'allowlist':list(ALLOW),'repaired_verified':repaired,'services':rows,'transient_failure_cleanup':{'enabled':True,'minimum_age_seconds':TRANSIENT_MIN_AGE_SECONDS,'max_per_run':TRANSIENT_MAX_PER_RUN,'cleared':cleared,'actions':transient_rows},'summary':{'repaired_verified':repaired,'transient_failures_cleared':cleared,'failed_now':failed_now},'bounded_restart_only':True,'persistent_units_reset_failed_authorized':False,'transient_reset_failed_only':True,'max_attempt_frequency_seconds':COOLDOWN}
    STATUS.parent.mkdir(parents=True,exist_ok=True); STATUS.write_text(json.dumps(out,indent=2)+'\n'); STATUS.chmod(0o644); print(json.dumps(out['summary'],sort_keys=True))
if __name__=='__main__':main()
