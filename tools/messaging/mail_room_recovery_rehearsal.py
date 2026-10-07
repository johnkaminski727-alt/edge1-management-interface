#!/usr/bin/env python3
"""Private mail snapshot and disposable restore. No production restore or delivery."""
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from tools.messaging.mail_room_readiness import save, ROOT

DATABASES={'correspondence':Path('/var/lib/wwcx-mail-room/correspondence.sqlite3'),
 'drafts':Path('/var/lib/wwcx-mail-room-drafts/drafts.sqlite3'),'security':Path('/var/lib/wwcx-mail-security/security.sqlite3')}
CONFIGS=['/etc/wwcx/outbound-mail','/etc/wwcx/mail-security-policy.json','/etc/wwcx/mail-security.env',
 '/etc/wwcx/mail-room.env','/etc/wwcx/mail-room-ava.env','/etc/wwcx/mail-gateway.env','/etc/wwcx/mail-commissioning.json',
 '/etc/clamav/wwcx-mail-clamd.conf','/etc/clamav/freshclam.conf','/etc/rspamd/local.d','/etc/rspamd/override.d']


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda:handle.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def files(root):
    if root.is_symlink():raise ValueError('Symlink refused')
    if root.is_file():return [root]
    result=[]
    for path in root.rglob('*'):
        if path.is_symlink():raise ValueError('Symlink refused')
        if path.is_file():result.append(path)
    return result


def counts(path):
    with sqlite3.connect('file:'+str(path)+'?mode=ro',uri=True) as db:
        if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Database integrity failed')
        if db.execute('PRAGMA foreign_key_check').fetchone():raise ValueError('Database relationships failed')
        return {name:db.execute('SELECT count(*) FROM "'+name.replace('"','""')+'"').fetchone()[0]
                for name, in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}


def main():
    if os.geteuid()!=0:raise SystemExit('Root required for private snapshot')
    os.umask(0o077);stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    snapshot=Path('/var/backups/wwcx-email-recovery')/('restore-rehearsal-'+stamp);snapshot.mkdir(mode=0o700)
    manifest={};db_counts={};archive=Path('/var/lib/wwcx-mail-gateway/inbound')
    source_files=files(archive)
    if sum(p.stat().st_size for p in source_files)>1024**3:raise SystemExit('Snapshot exceeds rehearsal budget; use full backup workflow')
    for name,path in DATABASES.items():
        target=snapshot/(name+'.sqlite3')
        with sqlite3.connect('file:'+str(path)+'?mode=ro',uri=True) as source, sqlite3.connect(target) as destination:source.backup(destination)
        target.chmod(0o600);db_counts[name]=counts(target);manifest[target.name]=digest(target)
    for root in [archive,*map(Path,CONFIGS),Path('/var/lib/wwcx-mail-updates')]:
        if not root.exists():continue
        selected=files(root)
        for path in selected:
            if root.is_dir() and any(part.startswith('backup-') for part in path.relative_to(root).parts):continue
            relative=Path('files')/str(path).lstrip('/');target=snapshot/relative;target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
            before=digest(path);shutil.copyfile(path,target);target.chmod(0o600)
            if before!=digest(target) or before!=digest(path):raise ValueError('Source changed during snapshot')
            manifest[str(relative)]=before
    rdb=snapshot/'redis.rdb'
    subprocess.run(['redis-cli','--rdb',str(rdb)],check=True,timeout=120,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    rdb.chmod(0o600);manifest[rdb.name]=digest(rdb)
    subprocess.run(['redis-check-rdb',str(rdb)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    (snapshot/'manifest.json').write_text(json.dumps({'files':manifest,'database_counts':db_counts},indent=2)+'\n')
    with tempfile.TemporaryDirectory(prefix='wwcx-mail-restore-') as temporary:
        restored=Path(temporary)
        for relative,expected in manifest.items():
            target=restored/relative;target.parent.mkdir(mode=0o700,parents=True,exist_ok=True);shutil.copyfile(snapshot/relative,target);target.chmod(0o600)
            if digest(target)!=expected:raise ValueError('Restored hash mismatch')
        for name in DATABASES:
            if counts(restored/(name+'.sqlite3'))!=db_counts[name]:raise ValueError('Restored rows mismatch')
        redis_dir=restored/'isolated-redis';redis_dir.mkdir(mode=0o700);shutil.copyfile(restored/'redis.rdb',redis_dir/'dump.rdb')
        sock=redis_dir/'redis.sock'
        proc=subprocess.Popen(['redis-server','--port','0','--unixsocket',str(sock),'--unixsocketperm','700',
          '--dir',str(redis_dir),'--dbfilename','dump.rdb','--save','','--appendonly','no','--maxmemory','64mb'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            for _ in range(100):
                if sock.exists():break
                if proc.poll() is not None:raise ValueError('Isolated Redis failed')
                time.sleep(.1)
            subprocess.run(['redis-cli','-s',str(sock),'PING'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            restored_keys=int(subprocess.check_output(['redis-cli','-s',str(sock),'DBSIZE'],text=True))
        finally:
            if proc.poll() is None:proc.terminate()
            proc.wait(timeout=10)
    report={'state':'passed','completed_at':datetime.now(timezone.utc).isoformat(),'sqlite_databases_verified':len(DATABASES),
      'files_hash_verified':len(manifest),'archive_files_verified':len(source_files),'redis_snapshot_loaded':True,
      'restored_redis_key_count':restored_keys,'snapshot_permissions':'root_only','production_restored':False,
      'mail_sent':False,'ai_called':False,'credentials_displayed':False,
      'scope':'Mail data/configuration restore only; full-server disaster recovery and external-provider recovery remain separate'}
    save(report,ROOT/'recovery-acceptance.json');print(json.dumps(report))

if __name__=='__main__':main()
