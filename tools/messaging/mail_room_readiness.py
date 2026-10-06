#!/usr/bin/env python3
"""Aggregate operational readiness. Never read message bodies or credentials."""
from datetime import datetime,timezone
import argparse
import hashlib
import json
import os
from pathlib import Path
import pwd
import shutil
import sqlite3
import subprocess
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from server.mail_security_updates import update_health
from server.mail_room_access import ACCESS_POLICY

ROOT=Path('/var/lib/wwcx-mail-room-reports')
DOMAINS=['ww.cx','creekco.ca','spiritcreekgardens.com','scgardens.ca','omegafx.com']
UNITS=['wwcx-mail-room','wwcx-outbound-mail-gateway','wwcx-mail-clamd','rspamd','redis-server','wwcx-mail-security-scan.timer','wwcx-mail-update-definitions.timer','wwcx-mail-update-packages.timer']


def query(path,sql):
    with sqlite3.connect('file:'+str(path)+'?mode=ro',uri=True,timeout=10) as db:return db.execute(sql).fetchall()


def backlog(archive,security,now=None):
    now=time.time() if now is None else now
    states={};warnings=[]
    try:
        states={r[0]:r[1] for r in query(security,'SELECT message_hash,state FROM decisions')}
        counts=dict(query(security,'SELECT state,count(*) FROM decisions GROUP BY state'))
    except (OSError,sqlite3.Error):
        counts=None;warnings.append('security_store_unavailable')
    total=0;pending=0;oldest=None;invalid=0
    for meta in archive.glob('*/*/metadata.json'):
        total+=1
        if total>100000: warnings.append('archive_inventory_limit');break
        try:
            if meta.is_symlink() or meta.stat().st_size>65536:raise ValueError('unsafe metadata')
            item=json.loads(meta.read_text());key=item.get('normalization',{}).get('message_id_sha256')
            if not key:raise ValueError('missing archive identity')
            if states.get(key) in {None,'pending'}:
                pending+=1;created=meta.stat().st_mtime;oldest=created if oldest is None else min(oldest,created)
        except (ValueError,OSError):invalid+=1
    age=max(0,now-oldest) if oldest else None
    if age is not None and age>900:warnings.append('pending_mail_older_than_15_minutes')
    if total>10000:warnings.append('scanner_archive_window_exceeded')
    if invalid:warnings.append('invalid_archive_metadata')
    return {'archives':total,'pending_or_unchecked':pending,'oldest_pending_age_seconds':age,'classification_counts':counts,
            'invalid_metadata':invalid,'worker_batch_limit':20,'worker_interval_seconds':60,'warnings':warnings}


def build():
    now=datetime.now(timezone.utc);warnings=[];services={}
    for unit in UNITS:
        state=subprocess.run(['systemctl','is-active',unit],capture_output=True,text=True,timeout=10).stdout.strip()
        services[unit]=state
        if state!='active':warnings.append('inactive_'+unit)
    worker=subprocess.run(['systemctl','show','wwcx-mail-security-scan','-p','Result','-p','ExecMainStatus'],capture_output=True,text=True,timeout=10).stdout
    worker=dict(line.split('=',1) for line in worker.splitlines() if '=' in line)
    if worker.get('Result')!='success' or worker.get('ExecMainStatus')!='0':warnings.append('last_security_scan_failed')
    queue=backlog(Path('/var/lib/wwcx-mail-gateway/inbound'),Path('/var/lib/wwcx-mail-security/security.sqlite3'));warnings+=queue['warnings']
    disk=shutil.disk_usage('/var/lib');free=disk.free;used_percent=round(100*disk.used/disk.total,1)
    if free<2*1024**3 or used_percent>=90:warnings.append('mail_storage_low')
    updates=update_health();warnings+=updates['warnings']
    registry=json.loads(Path('/etc/wwcx/outbound-mail/identities.json').read_text())
    from server.mail_identity_registry import sender_options
    senders=sender_options(registry)
    evidence_path=Path('/etc/wwcx/mail-commissioning.json')
    evidence=json.loads(evidence_path.read_text()) if evidence_path.exists() else {}
    try: dns=json.loads((ROOT/'dns-baseline.json').read_text())
    except (OSError,ValueError):dns={}
    domains=[]
    for domain in DOMAINS:
        record=evidence.get('domains',{}).get(domain,{})
        # Manual commissioning evidence is reported verbatim as recorded, never
        # inferred from an existing MX or successful local scanner probe.
        checks={name:record.get(name,'not_verified') for name in ['provider_credentials','public_dns','inbound_delivery','outbound_delivery','sender_authentication','rollback_rehearsal']}
        domains.append({'domain':domain,'registered_senders':sum(s['address'].endswith('@'+domain) for s in senders),
                        'live_sender_identities':sum(s['address'].endswith('@'+domain) and s['live_enabled'] for s in senders),
                        'dns_baseline':{'captured_at':dns.get('captured_at'),'source':dns.get('source'),'mx_answer_count':len(dns.get('domains',{}).get(domain,{}).get('mx',{}).get('answers',[]))},
                        'checks':checks,'commissioned':False,'sending_enabled':False,'migration_state':'not_migrated'})
    recovery=ROOT/'recovery-acceptance.json'
    try: recovery_record=json.loads(recovery.read_text())
    except (OSError,ValueError):recovery_record={'state':'not_rehearsed'}
    return {'contract':'wwcx.mail-readiness.v1','generated_at':now.isoformat(),'domains':domains,'services':services,
            'worker_last_result':worker,'backlog':queue,'storage':{'free_bytes':free,'used_percent':used_percent},
            'updates':updates,'warnings':sorted(set(warnings)),'access_policy':ACCESS_POLICY,'recovery':recovery_record,
            'dns_changes_applied':False,'send_enabled':False,'content_included':False}


def save(report,target):
    group=pwd.getpwnam('wwcx-mail-gateway').pw_gid;target.parent.mkdir(mode=0o750,exist_ok=True)
    temporary=target.with_suffix('.tmp');temporary.write_text(json.dumps(report,indent=2)+'\n');temporary.chmod(0o640);os.chown(temporary,0,group);temporary.replace(target)


def main():
    os.umask(0o077);save(build(),ROOT/'readiness.json');print(json.dumps({'readiness_generated':True,'content_included':False}))

if __name__=='__main__':main()
