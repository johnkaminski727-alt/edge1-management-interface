#!/usr/bin/env python3
from __future__ import annotations
import json, subprocess, time
from pathlib import Path
from datetime import datetime, timezone
STATE=Path('/var/lib/edge1-service-self-heal/state.json'); STATUS=Path('/var/www/edge1-status/service-self-heal/status.json')
ALLOW=('edge1-private-library-search.service','edge1-operator-mcp.service','edge1-operations-api.service','private-ai-browser-worker.service','wwcx-mail-room.service','bigbird-ai-gateway.service')
COOLDOWN=3600

def show(unit):
    q=subprocess.run(['systemctl','show',unit,'-p','ActiveState','-p','UnitFileState','-p','Result'],text=True,capture_output=True,check=False); d={}
    for line in q.stdout.splitlines():
        if '=' in line:k,v=line.split('=',1);d[k]=v
    return d
def load_state():
    try:return json.loads(STATE.read_text())
    except Exception:return {'attempts':{}}
def should_repair(props,last_attempt,now): return props.get('ActiveState')=='failed' and props.get('UnitFileState') in {'enabled','enabled-runtime'} and (not last_attempt or now-last_attempt>=COOLDOWN)
def main():
    now=time.time(); state=load_state(); attempts=state.setdefault('attempts',{}); rows=[]; repaired=0
    for unit in ALLOW:
        before=show(unit); last=float((attempts.get(unit) or {}).get('at',0) or 0); action='none'; after=before
        if should_repair(before,last,now):
            action='restart_attempted'; attempts[unit]={'at':now,'before':before.get('ActiveState')}; q=subprocess.run(['systemctl','restart',unit],text=True,capture_output=True,check=False,timeout=90); after=show(unit)
            if q.returncode==0 and after.get('ActiveState')=='active': action='restarted_verified'; repaired+=1
            else: action='restart_failed'
            attempts[unit]['result']=action
        rows.append({'unit':unit,'before':before.get('ActiveState','unknown'),'enabled':before.get('UnitFileState','unknown'),'action':action,'after':after.get('ActiveState','unknown'),'cooldown_seconds':COOLDOWN})
    STATE.parent.mkdir(parents=True,exist_ok=True); STATE.write_text(json.dumps(state,indent=2)+'\n'); STATE.chmod(0o600)
    out={'contract':'wwcx.service-self-heal.v1','generated_at':datetime.now(timezone.utc).isoformat(),'allowlist':list(ALLOW),'repaired_verified':repaired,'services':rows,'bounded_restart_only':True,'max_attempt_frequency_seconds':COOLDOWN}
    STATUS.parent.mkdir(parents=True,exist_ok=True); STATUS.write_text(json.dumps(out,indent=2)+'\n'); STATUS.chmod(0o644); print(json.dumps({'repaired_verified':repaired,'failed_now':sum(r['after']=='failed' for r in rows)},sort_keys=True))
if __name__=='__main__':main()
