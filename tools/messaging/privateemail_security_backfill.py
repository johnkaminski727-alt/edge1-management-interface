#!/usr/bin/env python3
"""Complete ordinary security inspections for imported history; never bypass checks."""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from email import policy
from email.parser import BytesParser
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from server.mail_room_security import archive_message_id, SecurityStore,message_hash
from tools.messaging.mail_room_security_scan import inspect,scanner_ready


def main():
    os.umask(0o077)
    security=SecurityStore()
    config=json.loads(Path('/etc/wwcx/mail-security-policy.json').read_text())
    config['domains']={**config.get('domains',{}),**security.settings()['domains']}
    identities=json.loads(Path('/etc/wwcx/outbound-mail/identities.json').read_text())
    config['catch_all_domains']=list(identities.get('catch_all_domains',{}))
    allowed=list(identities['sender_selection']['recipient_to_sender'])+[v['address'] for v in identities['sender_profiles'].values()]
    with sqlite3.connect('file:/var/lib/wwcx-mail-room/correspondence.sqlite3?mode=ro',uri=True) as db:
        wanted={message_hash(row[0]) for row in db.execute("SELECT message_id FROM correspondence WHERE source IN ('privateemail-historical-import','business159-domain-archive-import')")}
    def check(metadata):
        try:
            item=json.loads(metadata.read_text());key=item['normalization']['message_id_sha256']
            if key not in wanted:return None
            with security.connect() as db:
                old=db.execute('SELECT 1 FROM decisions WHERE message_hash=?',(key,)).fetchone()
            if old:return None
            raw=(metadata.parent/'message.eml').read_bytes();digest=hashlib.sha256(raw).hexdigest()
            if digest!=item['rfc822_sha256']:raise ValueError('integrity mismatch')
            mid=archive_message_id(raw,item)
            if message_hash(mid)!=key:raise ValueError('message identity mismatch')
            decision,attachments,indicators=inspect(raw,None,item['domain'],config)
            recipient=item['envelope_recipient'].lower()
            catch_all=recipient.rsplit('@',1)[-1] in config['catch_all_domains']
            if allowed and not catch_all and recipient not in {a.lower() for a in allowed} and decision['state']=='released':
                decision['state']='quarantine';decision['reasons'].append('unregistered_catch_all_recipient_review')
            security.write(mid,digest,decision,indicators)
            with sqlite3.connect('/var/lib/wwcx-mail-room-drafts/drafts.sqlite3',timeout=15) as db:
                payload={'attachments':attachments,'downloads_enabled':False,'quarantined':decision['state']=='quarantine','scanner_ready':scanner_ready(),'checked_at':time.time(),'indexed':True}
                db.execute('INSERT INTO attachment_checks VALUES (?,?,?,?) ON CONFLICT(message_hash) DO UPDATE SET archive_hash=excluded.archive_hash,payload=excluded.payload,checked=excluded.checked',(key,digest,json.dumps(payload),time.time()))
            return decision['state']
        except Exception:
            return 'error'
    counts={};checked=0;errors=0
    with ThreadPoolExecutor(max_workers=8) as pool:
        for state in pool.map(check, sorted(Path('/var/lib/wwcx-mail-gateway/inbound').glob('*/imap-*/metadata.json'))):
            if state is None:continue
            if state=='error':errors+=1;continue
            checked+=1;counts[state]=counts.get(state,0)+1
            if checked%20==0:print(json.dumps({'checked':checked,'states':counts,'errors':errors}),flush=True)
    print(json.dumps({'status':'complete','checked':checked,'states':counts,'errors':errors}),flush=True)

if __name__=='__main__':main()
