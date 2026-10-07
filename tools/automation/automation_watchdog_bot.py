#!/usr/bin/env python3
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT))
from tools.automation.automation_common import utcnow, upsert_library_document
INVENTORY=Path('/var/www/edge1-status/automation-center/inventory.json')
STATUS=Path('/var/www/edge1-status/automation-watchdog/status.json')
LIB=Path('/var/lib/bigbird-ai-library/library.sqlite3')
STATUS_SOURCES={
 'automation-center':Path('/var/www/edge1-status/automation-center/inventory.json'),
 'api-directory':Path('/var/www/edge1-status/api-directory/inventory.json'),
}
FRESHNESS_HOURS={
 'outstanding-actions':1, 'document-filing':2, 'drift-monitor':2, 'service-self-heal':2,
 'mail-domain-health':2, 'website-health':2, 'accounting-intake':2, 'ava-quality':2,
 'mail-learning':3, 'automation-center':1, 'api-directory':1,
 'backup-verification':36, 'certificate-expiry':36, 'credential-lifecycle':36,
 'storage-health':36, 'knowledge-consolidation':36, 'seo-audit':36,
}
def load(path:Path):
    try:return json.loads(path.read_text())
    except Exception:return {}
def parse_time(value):
    if not value:return None
    try:return datetime.fromisoformat(str(value).replace('Z','+00:00')).astimezone(timezone.utc)
    except Exception:return None
def build(now=None):
    now=now or datetime.now(timezone.utc); inv=load(INVENTORY); findings=[]
    custom=[t for t in inv.get('timers',[]) if t.get('custom')]
    for t in custom:
        name=str(t.get('timer') or 'unknown')
        if t.get('state')=='failed' or t.get('last_result') not in (None,'success'):
            findings.append({'kind':'timer_failure','severity':'high','subject':name,'detail':f"state={t.get('state')} result={t.get('last_result')} exit={t.get('exit_status')}",'action_level':'REVIEW-REQUIRED'})
        if t.get('enabled')=='enabled' and t.get('state') not in ('active','activating'):
            findings.append({'kind':'enabled_timer_inactive','severity':'high','subject':name,'detail':f"enabled timer state={t.get('state')}",'action_level':'REVIEW-REQUIRED'})
        nxt=parse_time(t.get('next_run'))
        if t.get('state')=='active' and nxt and (now-nxt).total_seconds()>600:
            findings.append({'kind':'timer_overdue','severity':'high','subject':name,'detail':f"next_run={t.get('next_run')} is overdue by more than 10 minutes",'action_level':'REVIEW-REQUIRED'})
    for p in inv.get('path_triggers',[]):
        if p.get('custom') and p.get('enabled')=='enabled' and p.get('state')!='active':
            findings.append({'kind':'path_trigger_inactive','severity':'medium','subject':p.get('path_unit'),'detail':f"enabled path trigger state={p.get('state')}",'action_level':'REVIEW-REQUIRED'})
    stale=[]
    for name,hours in FRESHNESS_HOURS.items():
        path=STATUS_SOURCES.get(name,Path('/var/www/edge1-status')/name/'status.json')
        if not path.is_file():
            stale.append({'name':name,'reason':'missing','threshold_hours':hours}); continue
        data=load(path); stamp=parse_time(data.get('generated_at') or data.get('checked_at') or data.get('generated_at_utc'))
        if stamp is None:
            age=(now-datetime.fromtimestamp(path.stat().st_mtime,timezone.utc)).total_seconds()/3600
        else: age=(now-stamp).total_seconds()/3600
        if age>hours: stale.append({'name':name,'reason':'stale','age_hours':round(age,2),'threshold_hours':hours})
    for x in stale:
        findings.append({'kind':'status_snapshot_'+x['reason'],'severity':'medium','subject':x['name'],'detail':json.dumps(x,sort_keys=True),'action_level':'REVIEW-REQUIRED'})
    state='attention' if any(f['severity']=='high' for f in findings) else 'warning' if findings else 'healthy'
    return {'contract':'wwcx.automation-watchdog.v1','generated_at':utcnow(),'state':state,'summary':{'custom_timers':len(custom),'findings':len(findings),'high':sum(f['severity']=='high' for f in findings),'stale_or_missing_snapshots':len(stale)},'findings':findings[:200],'production_mutation_performed':False}
def markdown(d):
    lines=['# Automation Watchdog','',f"Generated: {d['generated_at']}",f"State: **{d['state']}**",f"Findings: {d['summary']['findings']}",'','## Findings','']
    lines += [f"- **{x['severity']} · {x['subject']}** — {x['detail']}" for x in d['findings']] or ['- None.']
    lines += ['','The watchdog is read-only. It never enables, disables, restarts, or edits jobs.']
    return '\n'.join(lines)+'\n'
def main():
    d=build(); STATUS.parent.mkdir(parents=True,exist_ok=True); STATUS.write_text(json.dumps(d,indent=2)+'\n'); STATUS.chmod(0o644); upsert_library_document(LIB,ROOT,'operations/automation-watchdog/current.md','Automation Watchdog',markdown(d)); print(json.dumps(d['summary'],sort_keys=True))
if __name__=='__main__':main()
