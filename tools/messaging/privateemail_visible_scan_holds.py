#!/usr/bin/env python3
"""Represent scanner-blocked originals in Quarantine without projecting their bodies."""
from datetime import datetime,timezone
from email import policy
from email.parser import BytesParser
import hashlib
import json
import os
from pathlib import Path
import pwd
import sqlite3
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from tools.messaging.privateemail_archive_import import ROOT,DB,save,stage_import
from server.mail_room_security import SecurityStore
from mail_correspondence_store import MailCorrespondenceStore
from mail_local_rfc822_source import _date,_single_sender
from mail_edge1_gateway_source import _plain_text
from mail_correspondence_store import MAX_BODY_CHARS


def main():
    os.umask(0o077)
    backup=ROOT/'correspondence-before-visible-scan-holds.sqlite3'
    if not backup.exists():
        source=sqlite3.connect(DB);target=sqlite3.connect(backup);source.backup(target);source.close();target.close()
    reviewed=json.loads((ROOT/'remaining-scan-review.json').read_text())
    approved={r['path'] for r in reviewed if r['state']=='quarantined'}
    security=SecurityStore();store=MailCorrespondenceStore(DB,source='privateemail-historical-import',source_authoritative=True,source_scope='local_native');count=0
    for path in ROOT.glob('*/*/*.json'):
        item=json.loads(path.read_text())
        if item.get('projection',{}).get('status')!='held' or str(path) not in approved:continue
        raw=path.with_suffix('.eml').read_bytes();digest=hashlib.sha256(raw).hexdigest()
        if digest!=item['sha256']:raise ValueError('Original integrity failure')
        message=BytesParser(policy=policy.default).parsebytes(raw,headersonly=True)
        original=str(message.get('Message-ID','')).strip()
        try:mid=store._message_id(original)
        except Exception:mid='<privateemail-'+digest+'@archive.ww.cx>'
        try:occurred=_date(message)
        except Exception:
            occurred=item.get('provider_internaldate')
            if not occurred:raise ValueError('Provider receipt metadata required')
        try:text=_plain_text(BytesParser(policy=policy.default).parsebytes(raw))
        except Exception:text=''
        notice='Historical attachments remain blocked pending security review. The unchanged original is preserved in the private archive.'
        body=(notice+'\n\n'+text)[:MAX_BODY_CHARS] if text else notice+' Original body could not be projected safely.'
        payload={'message_id':mid,'provider_message_id':'privateemail:uid:'+item['uid'],'thread_id':'THREAD-HELD-'+digest[:24].upper(),'direction':'inbound','sender':_single_sender(message),'recipients':[item['account']],'subject':str(message.get('Subject','')),'body_text':body,'references':[],'occurred_at':occurred}
        security.write(mid,digest,{'state':'quarantine','hard_block':True,'scan_complete':False,'reasons':['historical_import_scan_block','historical_attachment_review_required'],'authentication':{'status':'not_verified'},'downloads_enabled':False})
        record=store.ingest(payload);stage_import(raw,item['account'],mid)
        directory=Path('/var/lib/wwcx-mail-gateway/inbound')/item['account'].rsplit('@',1)[1]/('imap-'+digest[:24]);meta=directory/'metadata.json';data=json.loads(meta.read_text());data['normalization']['import_security_hold']=True;data['normalization']['projection_kind']='quarantined_text';save(meta,data);user=pwd.getpwnam('wwcx-mail-gateway');os.chown(meta,user.pw_uid,user.pw_gid)
        item['previous_projection']=item['projection'];item['projection']={'status':'quarantined','kind':'quarantined_text','reason':'original_security_inspection_blocked','message_id_sha256':hashlib.sha256(mid.encode()).hexdigest()};save(path,item);count+=1
    save(ROOT/'visible-scan-holds-report.json',{'visible_quarantine_notices':count,'attachment_bytes_exposed':False,'originals_modified':False,'checked_at':datetime.now(timezone.utc).isoformat()});print(json.dumps({'visible_quarantine_notices':count}))

if __name__=='__main__':main()
