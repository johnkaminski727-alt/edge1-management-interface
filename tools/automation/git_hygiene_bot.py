#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os, pwd, grp, stat, subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO=Path('/opt/edge1-management-interface')
STATE=Path('/var/lib/edge1-git-hygiene')
STATUS=Path('/var/www/edge1-status/git-hygiene/status.json')
SOURCE_PREFIXES=('server/','tools/','tests/','deploy/','src/','docs/','bin/','config/automation/','config/edge1_operator/')

def run(*args): return subprocess.run(args,text=True,capture_output=True,check=False)
def git(*args): return run('git','-c',f'safe.directory={REPO}','-C',str(REPO),*args).stdout.strip()
def eligible_source(path:str)->bool: return path.startswith(SOURCE_PREFIXES)
def expected_mode(index_mode:str)->int|None:
    if index_mode=='100755': return 0o755
    if index_mode=='100644': return 0o644
    return None

def dirty_tracked()->set[str]:
    names=set()
    for args in (('diff','--name-only'),('diff','--cached','--name-only')):
        out=git(*args)
        names.update(x for x in out.splitlines() if x)
    return names

def tracked_entries():
    result=[]
    raw=run('git','-c',f'safe.directory={REPO}','-C',str(REPO),'ls-files','-s','-z').stdout
    for record in raw.split('\0'):
        if not record or '\t' not in record: continue
        meta,path=record.split('\t',1); mode=meta.split()[0]
        result.append((path,mode))
    return result

def _metadata_row(path:Path):
    s=path.lstat()
    return {'path':str(path.relative_to(REPO)),'uid':s.st_uid,'gid':s.st_gid,'mode':stat.S_IMODE(s.st_mode)}

def snapshot():
    st=REPO.stat(); owner=pwd.getpwuid(st.st_uid).pw_name; group=grp.getgrgid(st.st_gid).gr_name
    head=git('rev-parse','HEAD'); status=git('status','--porcelain=v1'); dirty=dirty_tracked()
    git_rows=[]
    for p in (REPO/'.git').rglob('*'):
        try:
            s=p.lstat()
            if p.is_symlink(): continue
            if s.st_uid==0 or s.st_gid==0: git_rows.append(_metadata_row(p))
        except OSError: pass
    source=[]; deferred_dirty=[]; deferred_sensitive=[]; eligible_dirs={}
    for rel,index_mode in tracked_entries():
        p=REPO/rel
        try:s=p.lstat()
        except OSError: continue
        if p.is_symlink(): continue
        desired=expected_mode(index_mode)
        if eligible_source(rel):
            parent=p.parent
            while parent!=REPO and str(parent).startswith(str(REPO)):
                eligible_dirs[str(parent.relative_to(REPO))]=parent
                parent=parent.parent
            # Preserve benign checkout umasks/group-write modes when the repository owner already owns the file.
            # Normalize Git mode only when ownership itself is wrong or owner access has been lost.
            owner_access=bool(s.st_mode & stat.S_IRUSR) and (desired != 0o755 or bool(s.st_mode & stat.S_IXUSR))
            mismatch=(s.st_uid!=st.st_uid or s.st_gid!=st.st_gid or not owner_access)
            if mismatch:
                row={**_metadata_row(p),'desired_uid':st.st_uid,'desired_gid':st.st_gid,'desired_mode':desired,'index_mode':index_mode}
                (deferred_dirty if rel in dirty else source).append(row)
        elif s.st_uid==0 or s.st_gid==0:
            deferred_sensitive.append(_metadata_row(p))
    dirs=[]
    for rel,p in sorted(eligible_dirs.items()):
        try:s=p.lstat()
        except OSError:continue
        if p.is_symlink():continue
        if s.st_uid!=st.st_uid or s.st_gid!=st.st_gid:
            dirs.append({**_metadata_row(p),'desired_uid':st.st_uid,'desired_gid':st.st_gid})
    return {'repo_owner':owner,'repo_group':group,'owner_uid':st.st_uid,'owner_gid':st.st_gid,'head':head,'status':status,'dirty':bool(status),'git_root_owned':git_rows,'tracked_source_mismatches':source,'tracked_dir_mismatches':dirs,'deferred_dirty':deferred_dirty,'deferred_sensitive':deferred_sensitive}

def _record_before(path:Path):
    s=path.lstat(); return (path,s.st_uid,s.st_gid,stat.S_IMODE(s.st_mode))
def _restore(changes):
    for p,uid,gid,mode in reversed(changes):
        if p.exists() and not p.is_symlink():
            os.chown(p,uid,gid); os.chmod(p,mode)

def apply_safe(before):
    if before['repo_owner']!='wwadmin': return {'applied':0,'reason':'repo_owner_not_wwadmin'}
    STATE.mkdir(parents=True,exist_ok=True); stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'); evidence=STATE/f'ownership-repair-{stamp}.json'; evidence.write_text(json.dumps(before,indent=2)+'\n'); evidence.chmod(0o600)
    changes=[]; changed=[]
    try:
        for row in before['git_root_owned']:
            p=REPO/row['path']
            if not p.exists() or p.is_symlink() or not str(p.resolve()).startswith(str((REPO/'.git').resolve())): continue
            changes.append(_record_before(p)); os.chown(p,before['owner_uid'],before['owner_gid']); changed.append(row['path'])
        for row in before['tracked_dir_mismatches']:
            p=REPO/row['path']
            if not p.exists() or p.is_symlink(): continue
            changes.append(_record_before(p)); os.chown(p,row['desired_uid'],row['desired_gid']); changed.append(row['path'])
        for row in before['tracked_source_mismatches']:
            p=REPO/row['path']
            if not p.exists() or p.is_symlink(): continue
            changes.append(_record_before(p)); os.chown(p,row['desired_uid'],row['desired_gid'])
            if row.get('desired_mode') is not None: os.chmod(p,row['desired_mode'])
            changed.append(row['path'])
        after=snapshot()
        if after['head']!=before['head'] or after['status']!=before['status']:
            _restore(changes); raise RuntimeError('Git state changed during hygiene repair; metadata rolled back')
    except Exception:
        if changes: _restore(changes)
        raise
    return {'applied':len(changed),'evidence':str(evidence),'git_metadata_repaired':len(before['git_root_owned']),'source_paths_repaired':len(before['tracked_source_mismatches'])+len(before['tracked_dir_mismatches']),'remaining_git_root_owned':len(after['git_root_owned']),'remaining_auto_repairable':len(after['tracked_source_mismatches'])+len(after['tracked_dir_mismatches']),'deferred_dirty':len(after['deferred_dirty']),'deferred_sensitive':len(after['deferred_sensitive']),'head_unchanged':True,'working_tree_unchanged':True}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--apply-safe',action='store_true'); a=ap.parse_args(); before=snapshot(); result=apply_safe(before) if a.apply_safe else {'applied':0,'reason':'dry_run'}
    remaining=int(result.get('remaining_git_root_owned',len(before['git_root_owned'])))+int(result.get('remaining_auto_repairable',len(before['tracked_source_mismatches'])+len(before['tracked_dir_mismatches'])))
    state='healthy' if remaining==0 else 'warning'
    summary={'git_metadata_root_owned_before':len(before['git_root_owned']),'tracked_source_mismatches_before':len(before['tracked_source_mismatches'])+len(before['tracked_dir_mismatches']),'repairs_applied':result.get('applied',0),'deferred_dirty':result.get('deferred_dirty',len(before['deferred_dirty'])),'deferred_sensitive':result.get('deferred_sensitive',len(before['deferred_sensitive'])),'remaining_auto_repairable':remaining}
    out={'contract':'wwcx.git-hygiene.v2','generated_at':datetime.now(timezone.utc).isoformat(),'state':state,'summary':summary,'before':{'head':before['head'],'dirty':before['dirty'],'repo_owner':before['repo_owner']},'result':result,'safe_scope':'ownership under .git plus clean tracked source ownership/mode in allowlisted source trees; dirty and sensitive config are deferred; content is unchanged'}
    STATUS.parent.mkdir(parents=True,exist_ok=True); STATUS.write_text(json.dumps(out,indent=2)+'\n'); STATUS.chmod(0o644); print(json.dumps({'state':state,**summary},sort_keys=True))
if __name__=='__main__': main()
