#!/usr/bin/env python3
from __future__ import annotations
import json, os, stat, subprocess
from datetime import datetime, timezone
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT))
from tools.automation.automation_common import utcnow, upsert_library_document
STATUS=Path('/var/www/edge1-status/credential-lifecycle/status.json')
LIB=Path('/var/lib/bigbird-ai-library/library.sqlite3')
# Paths only. File contents are never opened/read.
WATCH=[
 ('Edge1 agent shell token',Path('/etc/edge1-operator/mcp-token'),True,'edge1-agent-shell.service'),
 ('Edge1 operator environment',Path('/etc/edge1-operator/edge1-operator.env'),True,'edge1-operator-mcp.service'),
 ('Private AI browser worker environment',Path('/etc/wwcx/private-ai-browser-worker.env'),True,'private-ai-browser-worker.service'),
 ('Big Bird AI gateway environment',Path('/etc/bigbird-ai-gateway.env'),True,'bigbird-ai-gateway.service'),
 ('Network sensor environment',Path('/etc/default/wwcx-network-sensor'),False,None),
 ('Mining environment',Path('/etc/wwcx-mining/cpuminer.env'),True,'wwcx-cpu-miner.service'),
]
def service_loaded(unit):
    if not unit:return True
    q=subprocess.run(['systemctl','show',unit,'-p','LoadState','--value'],text=True,capture_output=True,check=False)
    return q.stdout.strip()=='loaded'
def item(label,path,sensitive,unit):
    try:s=path.stat()
    except FileNotFoundError:
        required=sensitive and service_loaded(unit)
        return {'label':label,'path':str(path),'present':False,'sensitive_expected':sensitive,'service':unit,'service_loaded':service_loaded(unit) if unit else None,'state':'missing' if required else 'optional_missing'}
    age=(datetime.now(timezone.utc)-datetime.fromtimestamp(s.st_mtime,timezone.utc)).total_seconds()/86400
    mode=stat.S_IMODE(s.st_mode); exposed=bool(mode & 0o007 or mode & 0o020) if sensitive else False
    age_state='critical_age' if sensitive and age>180 else 'review_age' if sensitive and age>90 else 'current'
    state='permissions_attention' if exposed else age_state
    return {'label':label,'path':str(path),'present':True,'sensitive_expected':sensitive,'service':unit,'service_loaded':service_loaded(unit) if unit else None,'owner_uid':s.st_uid,'owner_gid':s.st_gid,'mode':format(mode,'04o'),'age_days':round(age,1),'state':state}
def build():
    rows=[item(*x) for x in WATCH]
    attention=[x for x in rows if x['state'] in {'missing','permissions_attention','critical_age','review_age'}]
    result={'contract':'wwcx.credential-lifecycle.v1','generated_at':utcnow(),'state':'attention' if attention else 'healthy','items':rows,'attention_count':len(attention),'credential_contents_read':False,'secret_values_exposed':False,'automatic_rotation_performed':False,'rotation_authorized':False}
    STATUS.parent.mkdir(parents=True,exist_ok=True); STATUS.write_text(json.dumps(result,indent=2)+'\n'); STATUS.chmod(0o644)
    lines=['# Credential Lifecycle','',f"Generated: {result['generated_at']}",f"State: **{result['state']}** · attention items: {len(attention)}",'', '## Credential metadata','']
    for x in rows: lines.append(f"- **{x['label']}** — {x['state']} — present={x['present']} — mode={x.get('mode','n/a')} — age={x.get('age_days','n/a')} days — path `{x['path']}`")
    lines += ['','Only path/stat metadata is inspected. Credential contents and secret values are never read or published. Rotation remains review-required.']
    upsert_library_document(LIB,ROOT,'operations/credential-lifecycle/current.md','Credential Lifecycle','\n'.join(lines)+'\n')
    return result
if __name__=='__main__':
    d=build(); print(json.dumps({'state':d['state'],'attention_count':d['attention_count'],'items':len(d['items'])},sort_keys=True))
