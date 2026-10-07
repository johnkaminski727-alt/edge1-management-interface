#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os, stat, subprocess
from pathlib import Path
import sys
ROOT=Path('/opt/edge1-management-interface'); REPO=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(REPO))
from tools.automation.automation_common import utcnow, upsert_library_document
from tools.edge1_operator.check_ui_publication import STATE as UI_STATE, inventory as ui_inventory, safe_reconcile as ui_safe_reconcile
STATUS=Path('/var/www/edge1-status/drift-monitor/status.json'); LIB=Path('/var/lib/bigbird-ai-library/library.sqlite3')

def run(args): return subprocess.run(args,text=True,capture_output=True,check=False)
def git(*args): return run(['git','--no-optional-locks','-c',f'safe.directory={ROOT}','-C',str(ROOT),*args]).stdout.strip()
def service(unit):
    p=run(['systemctl','is-active',unit]); return p.stdout.strip() or 'unknown'
def git_metadata_access_issues():
    try:
        repo=ROOT.stat(); owner_uid,owner_gid=repo.st_uid,repo.st_gid
    except OSError:
        return ['.git']
    shared=git('config','--get','core.sharedRepository').strip().lower() in {'group','1','true','0660'}
    issues=[]
    for p in (ROOT/'.git').rglob('*'):
        try:
            s=p.lstat()
            if p.is_symlink(): continue
            if s.st_uid==owner_uid and s.st_gid==owner_gid: continue
            mode=stat.S_IMODE(s.st_mode)
            if shared and s.st_gid==owner_gid:
                if stat.S_ISDIR(s.st_mode) and (mode & 0o070)==0o070: continue
                rel=str(p.relative_to(ROOT))
                if rel.startswith('.git/objects/') and not stat.S_ISDIR(s.st_mode) and (mode & stat.S_IRGRP): continue
                if not stat.S_ISDIR(s.st_mode) and (mode & 0o060)==0o060: continue
            issues.append(str(p.relative_to(ROOT)))
        except OSError:
            issues.append(str(p.relative_to(ROOT)))
    return issues

def publication_state(apply_safe=False):
    try: data=json.loads(UI_STATE.read_text())
    except Exception: return {'state':'unavailable','rows':[],'safe_reconciled':0,'backup':None}
    rows=ui_inventory(data); conflicts=[r for r in rows if r['classification'] in {'live_only_conflict','diverged_conflict','unverifiable'}]
    safe=[r for r in rows if r['classification']=='baseline_stale_safe']; source_only=[r for r in rows if r['classification']=='source_only']
    reconciled=0; backup=None
    if apply_safe and safe and not conflicts:
        result=ui_safe_reconcile(data); reconciled=len(result.get('updated_files',[])); backup=result.get('backup'); rows=result['rows']
        conflicts=[r for r in rows if r['classification'] in {'live_only_conflict','diverged_conflict','unverifiable'}]
        safe=[r for r in rows if r['classification']=='baseline_stale_safe']; source_only=[r for r in rows if r['classification']=='source_only']
    state='conflict' if conflicts else 'baseline_stale' if safe else 'source_only' if source_only else 'in_sync'
    return {
      'state':state,'rows':rows,'safe_reconciled':reconciled,'backup':backup,
      'summary':{'in_sync':sum(r['classification']=='in_sync' for r in rows),'baseline_stale_safe':len(safe),'source_only':len(source_only),'conflicts':len(conflicts)},
      'source_only_files':[r['source'] for r in source_only],
      'conflict_files':[r['source'] for r in conflicts],
    }

def build(apply_safe=False):
    findings=[]; branch=git('branch','--show-current'); head=git('rev-parse','HEAD'); dirty=git('status','--porcelain')
    if dirty: findings.append({'kind':'git_working_tree','severity':'medium','state':'drift','detail':f'{len(dirty.splitlines())} working-tree entries present','action_level':'REVIEW-REQUIRED'})
    git_access_issues=git_metadata_access_issues()
    if git_access_issues: findings.append({'kind':'git_metadata_access','severity':'medium','state':'drift','detail':f'{len(git_access_issues)} Git metadata paths are not safely accessible to the repository owner/group','sample':git_access_issues[:8],'action_level':'AUTO-STAGE'})
    required=['edge1-operations-api.service','edge1-operator-mcp.service','edge1-private-library-search.service','wwcx-mail-room.service']; states={u:service(u) for u in required}
    for u,s in states.items():
        if s!='active': findings.append({'kind':'service_state','severity':'high','state':'drift','detail':f'{u} is {s}','action_level':'REVIEW-REQUIRED'})
    sockets=run(['ss','-ltnH']).stdout; wildcard=any(x in sockets for x in ('0.0.0.0:8097','[::]:8097','*:8097')); loopback='127.0.0.1:8097' in sockets
    if wildcard or not loopback: findings.append({'kind':'operations_api_boundary','severity':'critical' if wildcard else 'high','state':'drift','detail':'Operations API is not confirmed loopback-only on 8097.','action_level':'REVIEW-REQUIRED'})
    ui=publication_state(apply_safe)
    if ui['state']=='conflict': findings.append({'kind':'ui_publication_drift','severity':'medium','state':'drift','detail':f"{ui['summary']['conflicts']} live/source publication conflicts require review.",'sample':ui['conflict_files'][:8],'action_level':'REVIEW-REQUIRED'})
    elif ui['state']=='baseline_stale': findings.append({'kind':'ui_publication_baseline_stale','severity':'low','state':'drift','detail':f"{ui['summary']['baseline_stale_safe']} live files already match reviewed source; baseline refresh is safe.",'action_level':'AUTO-FIX'})
    result={'contract':'wwcx.edge1-drift-monitor.v2','generated_at':utcnow(),'repository':{'branch':branch,'head':head,'dirty':bool(dirty),'git_metadata_access_issues':len(git_access_issues),'root_owned_git_metadata':0},'services':states,'operations_api_loopback_only':loopback and not wildcard,'ui_publication':{'state':ui['state'],'summary':ui.get('summary',{}),'source_only_files':ui.get('source_only_files',[]),'safe_reconciled':ui.get('safe_reconciled',0),'backup':ui.get('backup')},'ui_publication_matches':ui['state'] in {'in_sync','source_only'},'summary':{'findings':len(findings),'critical':sum(x['severity']=='critical' for x in findings),'high':sum(x['severity']=='high' for x in findings),'safe_fix_candidates':sum(x['action_level'] in {'AUTO-STAGE','AUTO-FIX'} for x in findings)},'findings':findings,'mutation_performed':bool(ui.get('safe_reconciled')),'mutation_scope':'publication baseline metadata only' if ui.get('safe_reconciled') else None}
    return result

def md(d):
    lines=['# Edge1 Drift Monitor','',f"Generated: {d['generated_at']}",f"Repository: `{d['repository']['branch']}` `{d['repository']['head'][:12]}`",f"Findings: {d['summary']['findings']} (critical {d['summary']['critical']}, high {d['summary']['high']})",f"UI publication state: **{d['ui_publication']['state']}**",'']
    lines += [f"- **{x['severity'].upper()} · {x['kind']}** — {x['detail']} — `{x['action_level']}`" for x in d['findings']] or ['- No drift findings.']
    if d['ui_publication'].get('source_only_files'): lines += ['','Source-only UI changes (not published automatically):']+[f"- `{x}`" for x in d['ui_publication']['source_only_files']]
    lines += ['','Safe reconciliation may update publication baseline metadata only when live bytes already equal reviewed source bytes. It never publishes source-only UI changes.']; return '\n'.join(lines)+'\n'

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--apply-safe',action='store_true'); a=ap.parse_args(); d=build(a.apply_safe); STATUS.parent.mkdir(parents=True,exist_ok=True); STATUS.write_text(json.dumps(d,indent=2)+'\n'); STATUS.chmod(0o644); upsert_library_document(LIB,REPO,'operations/drift-monitor/current.md','Edge1 Drift Monitor',md(d)); print(json.dumps(d['summary']|{'ui_state':d['ui_publication']['state'],'ui_reconciled':d['ui_publication']['safe_reconciled']},sort_keys=True))
if __name__=='__main__': main()
