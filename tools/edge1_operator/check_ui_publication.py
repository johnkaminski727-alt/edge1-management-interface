#!/usr/bin/env python3
"""Protect UI publication from uncommitted source, live drift, and old revisions.

`reconcile-safe` updates publication bookkeeping only when the live file already
matches the reviewed repository source. It never copies or publishes UI files.
"""
from __future__ import annotations
import argparse, hashlib, json, os, shutil, subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path('/opt/edge1-management-interface')
STATE = Path('/var/lib/edge1-ui-publication/baseline.json')
BACKUPS = Path('/var/lib/edge1-ui-publication/backups')


def git(*args):
    return subprocess.check_output(
        ['git','--no-optional-locks','-c',f'safe.directory={ROOT}',*args],
        cwd=ROOT,text=True,
    ).strip()


def digest(path):
    path=Path(path)
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def classify_entry(baseline_sha, source_sha, live_sha):
    if live_sha is None or source_sha is None:
        return 'unverifiable'
    if live_sha == source_sha == baseline_sha:
        return 'in_sync'
    if live_sha == source_sha and live_sha != baseline_sha:
        return 'baseline_stale_safe'
    if live_sha == baseline_sha and source_sha != baseline_sha:
        return 'source_only'
    if source_sha == baseline_sha and live_sha != baseline_sha:
        return 'live_only_conflict'
    return 'diverged_conflict'


def inventory(data):
    rows=[]
    for item in data.get('files',[]):
        source=ROOT/item['source']; live=Path(item['live'])
        source_sha=digest(source); live_sha=digest(live); baseline_sha=item.get('sha256')
        rows.append({
            'item':item,'source':item['source'],'live':item['live'],
            'baseline_sha':baseline_sha,'source_sha':source_sha,'live_sha':live_sha,
            'classification':classify_entry(baseline_sha,source_sha,live_sha),
        })
    return rows


def safe_reconcile(data):
    rows=inventory(data)
    conflicts=[r for r in rows if r['classification'] in {'live_only_conflict','diverged_conflict','unverifiable'}]
    if conflicts:
        return {'applied':False,'reason':'conflict_present','rows':rows,'backup':None}
    safe=[r for r in rows if r['classification']=='baseline_stale_safe']
    if not safe:
        return {'applied':False,'reason':'nothing_to_reconcile','rows':rows,'backup':None}
    BACKUPS.mkdir(parents=True,exist_ok=True)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup=BACKUPS/f'baseline-before-safe-reconcile-{stamp}.json'
    shutil.copy2(STATE,backup); os.chmod(backup,0o600)
    for row in safe:
        row['item']['sha256']=row['live_sha']
    old_head=data.get('head')
    data['head']=git('rev-parse','HEAD')
    data['safe_reconciliation']={
        'at':datetime.now(timezone.utc).isoformat(),
        'previous_head':old_head,
        'updated_files':[r['source'] for r in safe],
        'source_only_files':[r['source'] for r in rows if r['classification']=='source_only'],
        'live_files_changed':False,
    }
    tmp=STATE.with_suffix('.tmp')
    tmp.write_text(json.dumps(data,indent=2)+'\n'); os.chmod(tmp,0o600); os.replace(tmp,STATE)
    return {'applied':True,'reason':'baseline_refreshed','rows':inventory(data),'backup':str(backup),'updated_files':[r['source'] for r in safe]}


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('mode',choices=['check','record','reconcile-safe']); args=parser.parse_args()
    if not STATE.is_file(): raise SystemExit('STOP: publication baseline is missing; reconcile live files first.')
    data=json.loads(STATE.read_text())
    if args.mode in {'check','reconcile-safe'}:
        if git('status','--porcelain'):
            if args.mode=='check': raise SystemExit('STOP: commit and review repository changes before publishing.')
            # Safe bookkeeping may proceed with unrelated dirty work because only files
            # whose live bytes equal their current source bytes are eligible.
        ancestor=subprocess.run(
            ['git','--no-optional-locks','-c',f'safe.directory={ROOT}','merge-base','--is-ancestor',data['head'],'HEAD'],
            cwd=ROOT,
        )
        if ancestor.returncode: raise SystemExit('STOP: this revision does not include the last published checkpoint.')
    if args.mode=='reconcile-safe':
        result=safe_reconcile(data)
        if result['reason']=='conflict_present':
            conflicts=[r['live'] for r in result['rows'] if r['classification'] in {'live_only_conflict','diverged_conflict','unverifiable'}]
            raise SystemExit('STOP: unsafe publication conflict:\n'+'\n'.join(conflicts))
        print(json.dumps({
            'ok':True,'applied':result['applied'],'reason':result['reason'],
            'updated_files':result.get('updated_files',[]),'backup':result.get('backup'),
            'source_only':[r['source'] for r in result['rows'] if r['classification']=='source_only'],
        },sort_keys=True))
        return
    errors=[]
    for row in inventory(data):
        if row['live_sha'] != row['baseline_sha']:
            if args.mode=='record' and row['live_sha']==row['source_sha']:
                row['item']['sha256']=row['live_sha']
            else: errors.append(row['live'])
    if errors: raise SystemExit('STOP: unreviewed live drift:\n'+'\n'.join(errors))
    if args.mode=='record':
        data['head']=git('rev-parse','HEAD'); tmp=STATE.with_suffix('.tmp'); tmp.write_text(json.dumps(data,indent=2)+'\n'); os.chmod(tmp,0o600); os.replace(tmp,STATE)
    print('PASS: UI publication '+args.mode)

if __name__=='__main__': main()
