#!/usr/bin/env python3
"""Index native archived attachments; scan decoded bytes and fail closed.

No downloads or release are enabled. Raw archives stay private; extracted bytes
exist only inside a private temporary directory for the trusted local scanner.
"""
import argparse
import email
import email.policy
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import time


def scanner_ready(database_dir=Path('/var/lib/clamav')):
    dbs = list(database_dir.glob('daily.c[lv]d'))
    if not shutil.which('clamscan') or not dbs: return False
    if Path('/etc/clamav/wwcx-mail-clamd.conf').exists():
        # A successful check with unchanged signatures is still fresh. Only the
        # root maintenance job can refresh this timestamp after loaded-version
        # verification and clean/EICAR probes.
        path=Path('/var/lib/wwcx-mail-updates/definitions.json')
        try:
            stat=path.stat()
            if path.is_symlink() or stat.st_uid!=0 or stat.st_mode & 0o022: return False
            checked=float(json.loads(path.read_text()).get('last_success') or 0)
            return time.time()-86400 < checked <= time.time()+300
        except (OSError, ValueError, TypeError): return False
    return max(p.stat().st_mtime for p in dbs)>time.time()-3*86400


def scan_bytes(data):
    if not scanner_ready():
        return 'unscanned_blocked'
    if Path('/etc/clamav/wwcx-mail-clamd.conf').exists() and not Path('/run/wwcx-mail-clamd/scan.sock').exists():
        return 'unscanned_blocked'
    if shutil.which('clamdscan') and Path('/run/wwcx-mail-clamd/scan.sock').exists():
        try:
            result=subprocess.run(['clamdscan','--config-file=/etc/clamav/wwcx-mail-clamd.conf','--stream','--no-summary','-'],input=data,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=90)
        except (subprocess.TimeoutExpired,OSError):
            return 'unscanned_blocked'
        return 'clean_download_disabled' if result.returncode==0 else 'quarantined' if result.returncode==1 else 'unscanned_blocked'
    with tempfile.TemporaryDirectory(prefix='mail-attachment-') as directory:
        path = Path(directory)/'attachment.bin'; path.write_bytes(data); path.chmod(0o600)
        try:
            result = subprocess.run(['clamscan','--no-summary','--max-filesize=25M','--max-scansize=30M','--alert-exceeds-max=yes','--alert-encrypted=yes',str(path)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=90)
        except (subprocess.TimeoutExpired, OSError):
            return 'unscanned_blocked'
    return 'clean_download_disabled' if result.returncode == 0 else 'quarantined' if result.returncode == 1 else 'unscanned_blocked'


def index_archive(root, database, scan=scan_bytes):
    count=0
    with sqlite3.connect(database,timeout=15) as db:
        db.execute('CREATE TABLE IF NOT EXISTS attachment_checks (message_hash TEXT PRIMARY KEY, archive_hash TEXT NOT NULL, payload TEXT NOT NULL, checked REAL NOT NULL)')
        for metadata in sorted(root.glob('*/*/metadata.json'), key=lambda p:p.stat().st_mtime, reverse=True)[:10000]:
            if count >= 25:break
            if metadata.is_symlink():continue
            item=json.loads(metadata.read_text()); message_hash=item.get('normalization',{}).get('message_id_sha256')
            if not message_hash:continue
            raw_path=metadata.parent/'message.eml'
            if raw_path.is_symlink() or raw_path.stat().st_size>30*1024*1024:continue
            raw=raw_path.read_bytes(); digest=hashlib.sha256(raw).hexdigest()
            if digest!=item.get('rfc822_sha256'):continue
            previous=db.execute('SELECT archive_hash,checked FROM attachment_checks WHERE message_hash=?',(message_hash,)).fetchone()
            if previous and previous[0]==digest and previous[1]>time.time()-3600:continue
            message=email.message_from_bytes(raw,policy=email.policy.default);attachments=[]
            for part in message.walk():
                if part.is_multipart() or not (part.get_filename() or part.get_content_disposition()=='attachment'):continue
                if len(attachments)>=30:break
                data=part.get_payload(decode=True) or b''
                filename=''.join(c for c in (part.get_filename() or 'attachment') if ord(c)>=32)[:180]
                state='oversize_blocked' if len(data)>25*1024*1024 else scan(data)
                attachments.append({'filename':filename,'size_bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'state':state})
            payload={'attachments':attachments,'downloads_enabled':False,'quarantined':any(a['state']=='quarantined' for a in attachments),'scanner_ready':scanner_ready(),'checked_at':time.time()}
            db.execute('INSERT INTO attachment_checks VALUES (?,?,?,?) ON CONFLICT(message_hash) DO UPDATE SET archive_hash=excluded.archive_hash,payload=excluded.payload,checked=excluded.checked',(message_hash,digest,json.dumps(payload),time.time()));db.commit();count+=1
        db.commit()
    return count


def main():
    p=argparse.ArgumentParser();p.add_argument('--archive-root',type=Path,required=True);p.add_argument('--database',type=Path,required=True);a=p.parse_args()
    import os;os.umask(0o077)
    print(json.dumps({'archives_checked':index_archive(a.archive_root,a.database),'scanner_ready':scanner_ready(),'downloads_enabled':False}))

if __name__=='__main__':main()
