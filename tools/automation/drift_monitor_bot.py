#!/usr/bin/env python3
from __future__ import annotations
import json, os, pwd, subprocess
from pathlib import Path
import sys
ROOT=Path('/opt/edge1-management-interface'); REPO=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(REPO))
from tools.automation.automation_common import utcnow, upsert_library_document
STATUS=Path('/var/www/edge1-status/drift-monitor/status.json'); LIB=Path('/var/lib/bigbird-ai-library/library.sqlite3')
def run(args): return subprocess.run(args,text=True,capture_output=True,check=False)
def git(*args): return run(['git','-c',f'safe.directory={ROOT}', '-C',str(ROOT),*args]).stdout.strip()
def service(unit):
    p=run(['systemctl','is-active',unit]); return p.stdout.strip() or 'unknown'
def build():
    findings=[]; branch=git('branch','--show-current'); head=git('rev-parse','HEAD'); dirty=git('status','--porcelain')
    if dirty: findings.append({'kind':'git_working_tree','severity':'medium','state':'drift','detail':f'{len(dirty.splitlines())} working-tree entries present','action_level':'REVIEW-REQUIRED'})
    root_owned=[]
    for p in (ROOT/'.git').rglob('*'):
        try:
            if p.is_file() and p.stat().st_uid==0: root_owned.append(str(p.relative_to(ROOT)))
        except OSError: pass
    if root_owned: findings.append({'kind':'git_metadata_ownership','severity':'medium','state':'drift','detail':f'{len(root_owned)} root-owned Git metadata files','sample':root_owned[:8],'action_level':'AUTO-STAGE'})
    required=['edge1-operations-api.service','edge1-operator-mcp.service','edge1-private-library-search.service','wwcx-mail-room.service']
    states={u:service(u) for u in required}
    for u,s in states.items():
        if s!='active': findings.append({'kind':'service_state','severity':'high','state':'drift','detail':f'{u} is {s}','action_level':'REVIEW-REQUIRED'})
    sockets=run(['ss','-ltnH']).stdout; wildcard=any(x in sockets for x in ('0.0.0.0:8097','[::]:8097','*:8097')); loopback='127.0.0.1:8097' in sockets
    if wildcard or not loopback: findings.append({'kind':'operations_api_boundary','severity':'critical' if wildcard else 'high','state':'drift','detail':'Operations API is not confirmed loopback-only on 8097.','action_level':'REVIEW-REQUIRED'})
    ui=run(['/usr/bin/python3',str(ROOT/'tools/edge1_operator/check_ui_publication.py'),'check']); ui_ok=ui.returncode==0
    if not ui_ok: findings.append({'kind':'ui_publication_drift','severity':'medium','state':'drift','detail':'Published UI differs from reviewed source; automatic overwrite is not authorized.','action_level':'REVIEW-REQUIRED'})
    result={'contract':'wwcx.edge1-drift-monitor.v1','generated_at':utcnow(),'repository':{'branch':branch,'head':head,'dirty':bool(dirty),'root_owned_git_metadata':len(root_owned)},'services':states,'operations_api_loopback_only':loopback and not wildcard,'ui_publication_matches':ui_ok,'summary':{'findings':len(findings),'critical':sum(x['severity']=='critical' for x in findings),'high':sum(x['severity']=='high' for x in findings),'safe_fix_candidates':sum(x['action_level']=='AUTO-STAGE' for x in findings)},'findings':findings,'mutation_performed':False}
    return result
def md(d):
    lines=['# Edge1 Drift Monitor','',f"Generated: {d['generated_at']}",f"Repository: `{d['repository']['branch']}` `{d['repository']['head'][:12]}`",f"Findings: {d['summary']['findings']} (critical {d['summary']['critical']}, high {d['summary']['high']})",'']
    lines += [f"- **{x['severity'].upper()} · {x['kind']}** — {x['detail']} — `{x['action_level']}`" for x in d['findings']] or ['- No drift findings.']
    lines += ['','Detection is read-only. No repository, service, listener, or published file was changed.']; return '\n'.join(lines)+'\n'
def main():
    d=build(); STATUS.parent.mkdir(parents=True,exist_ok=True); STATUS.write_text(json.dumps(d,indent=2)+'\n'); STATUS.chmod(0o644); upsert_library_document(LIB,REPO,'operations/drift-monitor/current.md','Edge1 Drift Monitor',md(d)); print(json.dumps(d['summary'],sort_keys=True))
if __name__=='__main__': main()
