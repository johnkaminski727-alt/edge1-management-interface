#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os, pwd, grp, subprocess
from datetime import datetime, timezone
from pathlib import Path
REPO=Path('/opt/edge1-management-interface'); STATE=Path('/var/lib/edge1-git-hygiene'); STATUS=Path('/var/www/edge1-status/git-hygiene/status.json')
def run(*args): return subprocess.run(args,text=True,capture_output=True,check=False)
def git(*args): return run('git','-c',f'safe.directory={REPO}','-C',str(REPO),*args).stdout.strip()
def snapshot():
    st=REPO.stat(); owner=pwd.getpwuid(st.st_uid).pw_name; group=grp.getgrgid(st.st_gid).gr_name
    head=git('rev-parse','HEAD'); status=git('status','--porcelain')
    rows=[]
    for p in (REPO/'.git').rglob('*'):
        try:
            s=p.lstat()
            if p.is_symlink(): continue
            if s.st_uid==0 or s.st_gid==0: rows.append({'path':str(p.relative_to(REPO)),'uid':s.st_uid,'gid':s.st_gid,'mode':oct(s.st_mode & 0o777)})
        except OSError: pass
    return {'repo_owner':owner,'repo_group':group,'owner_uid':st.st_uid,'owner_gid':st.st_gid,'head':head,'dirty':bool(status),'dirty_entries':len(status.splitlines()) if status else 0,'root_owned':rows}
def apply_safe(before):
    if before['repo_owner']!='wwadmin' or before['dirty']: return {'applied':0,'reason':'guard_not_satisfied'}
    STATE.mkdir(parents=True,exist_ok=True); stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'); evidence=STATE/f'ownership-repair-{stamp}.json'; evidence.write_text(json.dumps(before,indent=2)+'\n'); evidence.chmod(0o600)
    changed=[]
    for row in before['root_owned']:
        p=REPO/row['path']
        if not p.exists() or p.is_symlink() or not str(p.resolve()).startswith(str((REPO/'.git').resolve())): continue
        s=p.stat()
        if s.st_uid==0 or s.st_gid==0: os.chown(p,before['owner_uid'],before['owner_gid']); changed.append(row['path'])
    after=snapshot()
    if after['head']!=before['head'] or after['dirty']!=before['dirty']:
        for row in before['root_owned']:
            p=REPO/row['path']
            if p.exists() and not p.is_symlink(): os.chown(p,row['uid'],row['gid'])
        raise RuntimeError('Git state changed during ownership repair; ownership rolled back')
    return {'applied':len(changed),'evidence':str(evidence),'remaining_root_owned':len(after['root_owned']),'head_unchanged':True,'working_tree_unchanged':True}
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--apply-safe',action='store_true'); a=ap.parse_args(); before=snapshot(); result=apply_safe(before) if a.apply_safe else {'applied':0,'reason':'dry_run'}
    out={'contract':'wwcx.git-hygiene.v1','generated_at':datetime.now(timezone.utc).isoformat(),'before':{'head':before['head'],'dirty':before['dirty'],'root_owned_count':len(before['root_owned']),'repo_owner':before['repo_owner']},'result':result,'safe_scope':'ownership only under .git; content and modes unchanged'}
    STATUS.parent.mkdir(parents=True,exist_ok=True); STATUS.write_text(json.dumps(out,indent=2)+'\n'); STATUS.chmod(0o644); print(json.dumps({'root_owned_before':len(before['root_owned']),'applied':result.get('applied',0),'remaining':result.get('remaining_root_owned')},sort_keys=True))
if __name__=='__main__': main()
