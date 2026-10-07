#!/usr/bin/env python3
from __future__ import annotations
import json, re, subprocess
from datetime import datetime, timezone
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT))
from tools.automation.automation_common import utcnow, upsert_library_document
STATUS=Path('/var/www/edge1-status/update-readiness/status.json')
LIB=Path('/var/lib/bigbird-ai-library/library.sqlite3')
APT_LISTS=Path('/var/lib/apt/lists')
REBOOT=Path('/var/run/reboot-required')
REBOOT_PKGS=Path('/var/run/reboot-required.pkgs')

def run(*args): return subprocess.run(args,text=True,capture_output=True,check=False)
def apt_upgrades(text=None):
    if text is None: text=run('apt','list','--upgradable').stdout
    rows=[]
    for line in text.splitlines():
        line=line.strip()
        if not line or line.startswith('Listing') or '/' not in line: continue
        m=re.match(r'([^/]+)/([^\s]+)\s+([^\s]+)\s+([^\s]+)\s+\[upgradable from:\s*([^\]]+)\]',line)
        if not m: continue
        package,suite,new_version,arch,old_version=m.groups()
        rows.append({'package':package,'suite':suite,'new_version':new_version,'old_version':old_version,'arch':arch,'security':'security' in suite.lower(),'kernel':package.startswith(('linux-image','linux-headers','linux-libc'))})
    return rows

def simulation_plan(text=None):
    if text is None:
        result=run('apt-get','-s','full-upgrade')
        text=result.stdout
        exit_status=result.returncode
    else:
        exit_status=0
    installs=[]; removals=[]
    for line in text.splitlines():
        line=line.strip()
        if line.startswith('Inst '):
            parts=line.split()
            if len(parts)>=2: installs.append(parts[1])
        elif line.startswith('Remv '):
            parts=line.split()
            if len(parts)>=2: removals.append(parts[1])
    summary_match=re.search(r'(\d+) upgraded, (\d+) newly installed, (\d+) to remove and (\d+) not upgraded',text)
    counts={'upgraded':None,'newly_installed':None,'removed':None,'not_upgraded':None}
    if summary_match:
        values=[int(x) for x in summary_match.groups()]
        counts=dict(zip(counts,values))
    return {'simulation':'apt-get -s full-upgrade','exit_status':exit_status,'success':exit_status==0,
            'counts':counts,'install_or_upgrade_packages':installs[:250],'removal_packages':removals[:100],
            'removals_planned':bool(removals),'package_install_authorized':False,'mutation_performed':False}

def failed_units(text=None):
    if text is None: text=run('systemctl','--failed','--no-legend','--no-pager').stdout
    names=[]
    for line in text.splitlines():
        parts=line.replace('●','').split()
        if parts and parts[0].endswith('.service'): names.append(parts[0])
    out=[]
    for name in names:
        p=run('systemctl','show',name,'-p','Transient','-p','UnitFileState','-p','FragmentPath','-p','Result','-p','ExecMainStatus').stdout
        props={}
        for row in p.splitlines():
            if '=' in row:
                k,v=row.split('=',1); props[k]=v
        transient=props.get('Transient')=='yes' or '/run/systemd/transient/' in props.get('FragmentPath','') or props.get('UnitFileState')=='transient'
        out.append({'unit':name,'transient':transient,'unit_file_state':props.get('UnitFileState'),'result':props.get('Result'),'exit_status':props.get('ExecMainStatus')})
    return out

def apt_cache_age(now=None):
    now=now or datetime.now(timezone.utc); times=[]
    try:
        for p in APT_LISTS.iterdir():
            if p.is_file(): times.append(p.stat().st_mtime)
    except OSError: pass
    return None if not times else max(0,(now-datetime.fromtimestamp(max(times),timezone.utc)).total_seconds()/3600)

def evaluate(upgrades,failures,reboot_required=False,reboot_packages=(),running_kernel='',cache_age_hours=None,now=None):
    now=now or datetime.now(timezone.utc); persistent=[x for x in failures if not x.get('transient')]; transient=[x for x in failures if x.get('transient')]; security=[x for x in upgrades if x.get('security')]; kernel=[x for x in upgrades if x.get('kernel')]; findings=[]
    if persistent: findings.append({'kind':'persistent_failed_units','severity':'high','detail':f'{len(persistent)} persistent systemd units are failed: '+', '.join(x['unit'] for x in persistent[:10]),'action_level':'REVIEW-REQUIRED'})
    if reboot_required: findings.append({'kind':'reboot_required','severity':'high','detail':'A reboot is required to complete installed maintenance.','action_level':'REVIEW-REQUIRED'})
    if security: findings.append({'kind':'security_updates_pending','severity':'medium','detail':f'{len(security)} security-channel package updates are pending.','action_level':'AUTO-STAGE'})
    elif upgrades: findings.append({'kind':'updates_pending','severity':'low','detail':f'{len(upgrades)} package updates are pending.','action_level':'AUTO-STAGE'})
    if cache_age_hours is None or cache_age_hours>48: findings.append({'kind':'apt_metadata_stale','severity':'medium','detail':f'APT metadata age is {None if cache_age_hours is None else round(cache_age_hours,1)} hours.','action_level':'AUTO-STAGE'})
    state='attention' if any(x['severity']=='high' for x in findings) else 'warning' if any(x['severity']=='medium' for x in findings) else 'healthy'
    return {'contract':'wwcx.update-readiness.v1','generated_at':now.isoformat(),'state':state,'summary':{'pending_updates':len(upgrades),'security_updates':len(security),'kernel_updates':len(kernel),'persistent_failed_units':len(persistent),'transient_failed_units':len(transient),'reboot_required':bool(reboot_required),'apt_metadata_age_hours':None if cache_age_hours is None else round(cache_age_hours,2),'findings':len(findings),'high':sum(x['severity']=='high' for x in findings),'medium':sum(x['severity']=='medium' for x in findings)},'updates':upgrades[:200],'persistent_failed_units':persistent[:100],'transient_failed_units':transient[:100],'running_kernel':running_kernel,'reboot_packages':list(reboot_packages)[:100],'findings':findings,'package_install_authorized':False,'package_mutation_performed':False,'reboot_authorized':False,'reboot_performed':False}
def build():
    upgrades=apt_upgrades(); failures=failed_units(); plan=simulation_plan(); reboot_required=REBOOT.exists(); reboot_packages=[]
    if REBOOT_PKGS.is_file():
        try: reboot_packages=[x.strip() for x in REBOOT_PKGS.read_text().splitlines() if x.strip()]
        except OSError: pass
    kernel=run('uname','-r').stdout.strip()
    data=evaluate(upgrades,failures,reboot_required,reboot_packages,kernel,apt_cache_age())
    data['contract']='wwcx.update-readiness.v2'; data['simulation_plan']=plan
    return data
def markdown(d):
    s=d['summary']; lines=['# Edge1 Update & Maintenance Readiness','',f"Generated: {d['generated_at']}",f"State: **{d['state']}**",f"Pending packages: **{s['pending_updates']}** · security: **{s['security_updates']}** · kernel-related: **{s['kernel_updates']}**",f"Persistent failed units: **{s['persistent_failed_units']}** · transient failed units: **{s['transient_failed_units']}** · reboot required: **{s['reboot_required']}**",f"Running kernel: `{d['running_kernel']}`",'', '## Findings','']
    lines += [f"- **{x['severity']} · {x['kind']}** — {x['detail']} — `{x['action_level']}`" for x in d['findings']] or ['- None.']
    plan=d.get('simulation_plan') or {}; counts=plan.get('counts') or {}
    lines += ['','## Simulated transaction','',f"- Simulation: `{plan.get('simulation','unavailable')}`",f"- Success: **{plan.get('success')}**",f"- Upgraded: **{counts.get('upgraded')}** · newly installed: **{counts.get('newly_installed')}** · removals: **{counts.get('removed')}** · held back: **{counts.get('not_upgraded')}**",f"- Package removals planned: **{plan.get('removals_planned',False)}**"]
    if d['updates']:
        lines += ['','## Pending updates',''] + [f"- `{x['package']}` {x['old_version']} → {x['new_version']} ({x['suite']})" for x in d['updates'][:60]]
    lines += ['','This bot is stage-only. It does not refresh repositories, install packages, restart services, or reboot Edge1.']; return '\n'.join(lines)+'\n'
def main():
    d=build(); STATUS.parent.mkdir(parents=True,exist_ok=True); STATUS.write_text(json.dumps(d,indent=2)+'\n'); STATUS.chmod(0o644); upsert_library_document(LIB,ROOT,'operations/update-readiness/current.md','Edge1 Update & Maintenance Readiness',markdown(d)); print(json.dumps(d['summary'],sort_keys=True))
if __name__=='__main__':main()
