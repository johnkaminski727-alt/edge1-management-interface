#!/usr/bin/env python3
"""Complete ordinary security inspections for imported history; never bypass checks."""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import time
from email import policy
from email.parser import BytesParser
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from server.mail_room_security import SecurityStore,message_hash
from tools.messaging.mail_room_security_scan import inspect,scanner_ready


def main():
    os.umask(0o077)
    security=SecurityStore()
    config=json.loads(Path('/etc/wwcx/mail-security-policy.json').read_text())
    config['domains']={**config.get('domains',{}),**security.settings()['domains']}
    identities=json.loads(Path('/etc/wwcx/outbound-mail/identities.json').read_text())
    allowed=list(identities['sender_selection']['recipient_to_sender'])+[v['address'] for v in identities['sender_profiles'].values()]
    with sqlite3.connect('file:/var/lib/wwcx-mail-room/correspondence.sqlite3?mode=ro',uri=True) as db:
        wanted={message_hash(row[0]) for row in db.execute("SELECT message_id FROM correspondence WHERE source='privateemail-historical-import'")}
    counts={};checked=0;errors=0
    for metadata in sorted(Path('/var/lib/wwcx-mail-gateway/inbound').glob('*/imap-*/metadata.json')):
        try:
            item=json.loads(metadata.read_text());key=item['normalization']['message_id_sha256']
            if key not in wanted:continue
            with security.connect() as db:
                old=db.execute('SELECT 1 FROM decisions WHERE message_hash=?',(key,)).fetchone()
            if old:continue
            raw=(metadata.parent/'message.eml').read_bytes();digest=hashlib.sha256(raw).hexdigest()
            if digest!=item['rfc822_sha256']:raise ValueError('integrity mismatch')
            mid=str(BytesParser(policy=policy.default).parsebytes(raw,headersonly=True).get('Message-ID','')).strip()
            if message_hash(mid)!=key:raise ValueError('message identity mismatch')
            decision,attachments,indicators=inspect(raw,None,item['domain'],config)
            if allowed and item['envelope_recipient'].lower() not in {a.lower() for a in allowed} and decision['state']=='released':
                decision['state']='quarantine';decision['reasons'].append('unregistered_catch_all_recipient_review')
            security.write(mid,digest,decision,indicators)
            with sqlite3.connect('/var/lib/wwcx-mail-room-drafts/drafts.sqlite3',timeout=15) as db:
                payload={'attachments':attachments,'downloads_enabled':False,'quarantined':decision['state']=='quarantine','scanner_ready':scanner_ready(),'checked_at':time.time(),'indexed':True}
                db.execute('INSERT INTO attachment_checks VALUES (?,?,?,?) ON CONFLICT(message_hash) DO UPDATE SET archive_hash=excluded.archive_hash,payload=excluded.payload,checked=excluded.checked',(key,digest,json.dumps(payload),time.time()))
            checked+=1;counts[decision['state']]=counts.get(decision['state'],0)+1
            if checked%20==0:print(json.dumps({'checked':checked,'states':counts,'errors':errors}),flush=True)
        except Exception:
            errors+=1
    print(json.dumps({'status':'complete','checked':checked,'states':counts,'errors':errors}),flush=True)

if __name__=='__main__':main()
