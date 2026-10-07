#!/usr/bin/env python3
"""Export a sanitized inventory of Edge1 background automation."""
from __future__ import annotations
import datetime as dt
import json
import re
import subprocess
from pathlib import Path

OUTPUT=Path('/var/www/edge1-status/automation-center/inventory.json')
CUSTOM_PREFIXES=('edge1-','wwcx-','bigbird-','ava-')
CONTINUOUS_TOKENS=('worker','collector','poller','monitor','watch','gateway','relay','broker','sync','reconcile','maintenance','exporter','scanner','sensor')

STATUS_ALIASES={
 'edge1-accounting-intake.service':'accounting-intake',
 'edge1-action-lifecycle.service':'action-lifecycle',
 'edge1-api-surface-health.service':'api-surface-health',
 'edge1-automation-watchdog.service':'automation-watchdog',
 'edge1-ava-quality-control.service':'ava-quality',
 'edge1-backup-verification.service':'backup-verification',
 'edge1-catalog-consistency.service':'catalog-consistency',
 'edge1-certificate-expiry.service':'certificate-expiry',
 'edge1-credential-lifecycle.service':'credential-lifecycle',
 'edge1-document-filing.service':'document-filing',
 'edge1-domain-renewal.service':'domain-renewal',
 'edge1-drift-monitor.service':'drift-monitor',
 'edge1-evidence-integrity.service':'evidence-integrity',
 'edge1-git-hygiene.service':'git-hygiene',
 'edge1-knowledge-consolidation.service':'knowledge-consolidation',
 'edge1-mail-domain-health.service':'mail-domain-health',
 'edge1-mail-learning.service':'mail-learning',
 'edge1-outstanding-actions.service':'outstanding-actions',
 'edge1-seo-audit.service':'seo-audit',
 'edge1-service-self-heal.service':'service-self-heal',
 'edge1-security-baseline.service':'security-baseline',
 'edge1-storage-health.service':'storage-health',
 'edge1-update-readiness.service':'update-readiness',
 'edge1-website-health.service':'website-health',
 'edge1-weekly-executive-briefing.service':'executive-briefing',
}
SAFE_STATUS_KEYS=('state','generated_at','generated_at_utc','checked_at')
SAFE_SUMMARY_KEYS={
 'total','high','medium','low','findings','issues','attention_count','review_items','active','new',
 'resolved_this_run','resolved_last_7d','reopened','listeners','added','removed','unattributed',
 'live_products','fallback_active','fallback_inactive','pages_checked','sites','custom_timers',
 'stale_or_missing_snapshots','documents','filed','unfiled','healthy','warning','attention',
 'domains','expiring_180d','expiring_60d','expiring_30d','lookup_failures','nearest_expiry_days',
 'pending_updates','security_updates','kernel_updates','persistent_failed_units','transient_failed_units','reboot_required','apt_metadata_age_hours',
 'repaired_verified','transient_failures_cleared','failed_now',
}

def _safe_scalar(value):
    if value is None or isinstance(value,(bool,int,float)): return value
    if isinstance(value,str): return value[:160]
    return None

def status_projection(service):
    slug=STATUS_ALIASES.get(service or '')
    if not slug: return None
    path=Path('/var/www/edge1-status')/slug/'status.json'
    if not path.is_file(): return {'slug':slug,'available':False,'status_url':f'/edge1-ops/status/{slug}/status.json'}
    try: data=json.loads(path.read_text())
    except (OSError,json.JSONDecodeError): return {'slug':slug,'available':False,'status_url':f'/edge1-ops/status/{slug}/status.json'}
    out={'slug':slug,'available':True,'status_url':f'/edge1-ops/status/{slug}/status.json'}
    for key in SAFE_STATUS_KEYS:
        if key in data:
            value=_safe_scalar(data.get(key))
            if value is not None: out[key]=value
    summary=data.get('summary') if isinstance(data.get('summary'),dict) else {}
    safe={}
    for key,value in summary.items():
        if key in SAFE_SUMMARY_KEYS:
            scalar=_safe_scalar(value)
            if scalar is not None: safe[key]=scalar
    if safe: out['summary']=safe
    return out
READ_ONLY_TOKENS=('export','status','observation','telemetry','search','readiness','summary','report','inventory','health','history','timeline','trends','correlation','briefing')
AUTO_STAGE_TOKENS=('candidate','intake','import','scan','classification','archive','stager','index')
READ_ONLY_ALLOW={
 'edge1-outstanding-actions.service','edge1-drift-monitor.service','edge1-backup-verification.service',
 'edge1-mail-restore-rehearsal.service','edge1-certificate-expiry.service','edge1-storage-health.service',
 'edge1-weekly-executive-briefing.service','edge1-mail-domain-health.service','edge1-knowledge-consolidation.service','edge1-website-health.service','edge1-seo-audit.service','edge1-security-baseline.service','edge1-domain-renewal.service','edge1-update-readiness.service'
}
AUTO_STAGE_ALLOW={'edge1-document-filing.service'}
AUTO_FIX_ALLOW={
 'edge1-contacts-maintenance.service','edge1-egress-reconcile.service','edge1-spamhaus-refresh.service',
 'edge1-navigation-export.service','wwcx-vpn-registration-sync.service','wwcx-mail-security-scan.service',
 'wwcx-suricata-update.service','edge1-dropbox-backup.service','edge1-git-hygiene.service','edge1-service-self-heal.service'
}

def run(*args):
    return subprocess.run(args,text=True,capture_output=True,check=False).stdout.strip()

def props(unit,*names):
    out=run('systemctl','show',unit,*sum((['-p',n] for n in names),[]))
    result={}
    for line in out.splitlines():
        if '=' in line:
            k,v=line.split('=',1); result[k]=v
    return result

def clean_description(value):
    value=' '.join((value or '').split())
    return value[:240]

def classify(unit,description):
    text=(unit+' '+description).lower()
    if unit in AUTO_FIX_ALLOW: return 'AUTO-FIX'
    if unit in READ_ONLY_ALLOW: return 'READ-ONLY'
    if unit in AUTO_STAGE_ALLOW: return 'AUTO-STAGE'
    if any(x in text for x in READ_ONLY_TOKENS): return 'READ-ONLY'
    if any(x in text for x in AUTO_STAGE_TOKENS): return 'AUTO-STAGE'
    return 'REVIEW-REQUIRED'

def _stamp(usec):
    try:
        value=int(usec or 0)
    except (TypeError,ValueError):
        return None
    if value <= 0: return None
    return dt.datetime.fromtimestamp(value/1_000_000,dt.timezone.utc).isoformat()

def _schedule(unit):
    text=run('systemctl','cat',unit)
    allowed=('OnCalendar=','OnUnitActiveSec=','OnUnitInactiveSec=','OnBootSec=','OnStartupSec=','RandomizedDelaySec=')
    values=[]
    for line in text.splitlines():
        line=line.strip()
        if line.startswith(allowed) and line not in values: values.append(line)
    return '; '.join(values)[:500] or None

def timer_inventory():
    names=run('systemctl','list-unit-files','--type=timer','--no-legend','--no-pager').splitlines()
    try:
        runtime=json.loads(run('systemctl','list-timers','--all','--no-pager','--output=json') or '[]')
    except json.JSONDecodeError:
        runtime=[]
    timing={x.get('unit'):x for x in runtime if isinstance(x,dict) and x.get('unit')}
    timers=[]
    for row in names:
        if not row.strip(): continue
        fields=row.split(); unit=fields[0]; unit_file_state=fields[1] if len(fields)>1 else 'unknown'
        p=props(unit,'Id','Description','ActiveState','UnitFileState','Unit')
        rt=timing.get(unit,{})
        service=p.get('Unit') or rt.get('activates') or (unit[:-6]+'.service' if unit.endswith('.timer') else '')
        sp=props(service,'Description','ActiveState','SubState','Result','ExecMainStatus') if service else {}
        timers.append({
          'timer':unit,'description':clean_description(p.get('Description')),'state':p.get('ActiveState','unknown'),
          'enabled':p.get('UnitFileState') or unit_file_state,'next_run':_stamp(rt.get('next')),
          'last_run':_stamp(rt.get('last')),'schedule':_schedule(unit),
          'service':service or None,'service_description':clean_description(sp.get('Description')),
          'service_state':sp.get('ActiveState','unknown'),'service_substate':sp.get('SubState','unknown'),
          'last_result':sp.get('Result') or None,'exit_status':sp.get('ExecMainStatus') or None,
          'action_level':classify(service or unit,sp.get('Description') or p.get('Description','')),
          'custom':unit.startswith(CUSTOM_PREFIXES),
          'bot_status':status_projection(service),
        })
    timers.sort(key=lambda x:(not x['custom'],x['timer']))
    return timers

def path_inventory():
    rows=run('systemctl','list-unit-files','--type=path','--no-legend','--no-pager').splitlines()
    items=[]
    for row in rows:
        if not row.strip(): continue
        fields=row.split(); unit=fields[0]
        p=props(unit,'Description','ActiveState','UnitFileState','Unit','Paths','Triggers')
        service=p.get('Unit') or p.get('Triggers') or None
        items.append({
          'path_unit':unit,'description':clean_description(p.get('Description')),'state':p.get('ActiveState','unknown'),
          'enabled':p.get('UnitFileState') or (fields[1] if len(fields)>1 else 'unknown'),'service':service,
          'watched_paths':p.get('Paths') or None,'action_level':classify(service or unit,p.get('Description','')),
          'custom':unit.startswith(CUSTOM_PREFIXES),
        })
    return sorted(items,key=lambda x:(not x['custom'],x['path_unit']))

def cron_inventory():
    sources=[Path('/etc/crontab')]
    cron_d=Path('/etc/cron.d')
    if cron_d.is_dir(): sources.extend(sorted(x for x in cron_d.iterdir() if x.is_file()))
    items=[]
    for source in sources:
        try: lines=source.read_text(errors='ignore').splitlines()
        except OSError: continue
        for line in lines:
            line=line.strip()
            if not line or line.startswith('#') or '=' in line.split()[0]: continue
            parts=line.split()
            if len(parts)<7: continue
            schedule=' '.join(parts[:5]); user=parts[5]
            items.append({'source':str(source),'schedule':schedule,'user':user,'command':'redacted','action_level':'REVIEW-REQUIRED'})
    return items

def continuous_inventory(timer_services):
    rows=run('systemctl','list-units','--type=service','--state=running','--no-legend','--no-pager').splitlines()
    result=[]
    for row in rows:
        if not row.strip(): continue
        unit=row.split()[0]
        if not unit.startswith(CUSTOM_PREFIXES) or unit in timer_services: continue
        p=props(unit,'Description','ActiveState','SubState','MainPID','ExecMainStartTimestamp','Restart')
        text=(unit+' '+p.get('Description','')).lower()
        if not any(token in text for token in CONTINUOUS_TOKENS): continue
        result.append({
          'service':unit,'description':clean_description(p.get('Description')),'state':p.get('ActiveState','unknown'),
          'substate':p.get('SubState','unknown'),'started_at':p.get('ExecMainStartTimestamp') or None,
          'restart_policy':p.get('Restart') or None,'action_level':classify(unit,p.get('Description','')),
        })
    return sorted(result,key=lambda x:x['service'])

def main():
    timers=timer_inventory(); timer_services={x['service'] for x in timers if x.get('service')}
    continuous=continuous_inventory(timer_services); paths=path_inventory(); cron=cron_inventory()
    failures=sum(1 for x in timers if x['service_state']=='failed' or x['last_result'] not in (None,'','success'))
    data={
      'contract':'wwcx.edge1-automation-inventory.v1','generated_at':dt.datetime.now(dt.timezone.utc).isoformat(),
      'summary':{'timers':len(timers),'custom_timers':sum(x['custom'] for x in timers),'continuous_workers':len(continuous),'path_triggers':len(paths),'custom_path_triggers':sum(x['custom'] for x in paths),'cron_jobs':len(cron),'failed_or_non_success':failures},
      'timers':timers,'continuous_services':continuous,'path_triggers':paths,'cron_jobs':cron,
      'safety':{'inventory_read_only':True,'secrets_exposed':False,'action_classification_conservative':True}
    }
    OUTPUT.parent.mkdir(parents=True,exist_ok=True); OUTPUT.write_text(json.dumps(data,indent=2)+'\n'); OUTPUT.chmod(0o644)
    print(json.dumps(data['summary'],sort_keys=True))
if __name__=='__main__': main()
