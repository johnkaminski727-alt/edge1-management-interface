#!/usr/bin/env python3
"""Recover legacy headers into an explicit local projection; originals stay intact.
Only IMAP INTERNALDATE is fetched, with EXAMINE and UIDVALIDITY validation.
No message bodies, addresses or credential values are logged.
"""
import collections
from datetime import datetime
from email import policy
from email.parser import BytesParser
from email.utils import getaddresses,format_datetime
import hashlib
import imaplib
import json
from pathlib import Path
import re
import sqlite3
import ssl
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from tools.messaging.privateemail_archive_import import ROOT,DB,readable_bytes,stage_import,save
from mail_correspondence_store import MailCorrespondenceStore
import mail_local_rfc822_source as source


def projection(raw,account,internal_date):
    digest=hashlib.sha256(raw).hexdigest();readable,_=readable_bytes(raw)
    message=BytesParser(policy=policy.default).parsebytes(readable);changes={}
    try:source._canonical_message_id(message.get('Message-ID'),'Message-ID')
    except Exception:
        if message.get('Message-ID') is not None:del message['Message-ID']
        message['Message-ID']='<privateemail-'+digest+'@archive.ww.cx>'
        changes['message_id_source']='raw_archive_sha256'
    for header in ['References','In-Reply-To']:
        try:source._message_ids(message.get(header),header)
        except Exception:
            del message[header];changes[header]='invalid_header_retained_in_original_only'
    try:source._recipients(message)
    except Exception:
        for header in ['To','Cc','Delivered-To']:del message[header]
        message['Delivered-To']=account;changes['recipient_source']='physical_provider_mailbox'
    try:source._date(message)
    except Exception:
        if not internal_date:raise ValueError('provider_receipt_date_required')
        if message.get('Date') is not None:del message['Date']
        message['Date']=format_datetime(datetime.fromisoformat(internal_date))
        changes['date_source']='provider_imap_internaldate'
    return message.as_bytes(),changes


def main():
    receipt_only='--receipt-metadata-only' in sys.argv
    counts=collections.Counter();grouped={}
    for path in ROOT.glob('*/*/*.json'):
        item=json.loads(path.read_text())
        if item.get('projection',{}).get('reason')==('malware_scan_not_clean' if receipt_only else 'LocalMailSourceError'):
            grouped.setdefault(item['account'],{}).setdefault((item['folder'],item['uidvalidity']),[]).append((path,item))
    store=MailCorrespondenceStore(DB,source='privateemail-historical-import',source_authoritative=True,source_scope='local_native')
    for account,folders in grouped.items():
        client=None
        try:
            credentials=json.loads((Path('/etc/wwcx/privateemail-import')/(account+'.json')).read_text())
            client=imaplib.IMAP4_SSL('mail.privateemail.com',993,ssl_context=ssl.create_default_context(),timeout=45)
            client.authenticate('PLAIN',lambda _: ('\x00'+credentials['username']+'\x00'+credentials['password']).encode());credentials.clear()
            for (folder,validity),items in folders.items():
                status,_=client.select(folder,readonly=True)
                if status!='OK' or client.response('UIDVALIDITY')[1][0].decode()!=validity:raise ValueError('folder_identity_changed')
                status,rows=client.uid('FETCH',','.join(item['uid'] for _,item in items),'(UID INTERNALDATE)')
                if status!='OK':raise ValueError('receipt_metadata_unavailable')
                dates={}
                for row in rows:
                    if not isinstance(row,bytes):continue
                    match=re.search(rb'UID (\d+).*INTERNALDATE "([^"]+)"',row)
                    if not match:match=re.search(rb'INTERNALDATE "([^"]+)".*UID (\d+)',row);reverse=True
                    else:reverse=False
                    if match:
                        uid,date=(match.group(2),match.group(1)) if reverse else match.groups()
                        dates[uid.decode()]=datetime.strptime(date.decode().strip(),'%d-%b-%Y %H:%M:%S %z').isoformat()
                for path,item in items:
                    try:
                        if receipt_only:
                            if item['uid'] not in dates:raise ValueError('provider_receipt_date_required')
                            item['provider_internaldate']=dates[item['uid']];save(path,item);counts['receipt_metadata_recovered']+=1;continue
                        raw=path.with_suffix('.eml').read_bytes()
                        if hashlib.sha256(raw).hexdigest()!=item['sha256']:raise ValueError('integrity_failure')
                        data,changes=projection(raw,account,dates.get(item['uid']))
                        record=source.normalize_rfc822(data,store,direction='outbound' if folder.strip('"').lower()=='sent' else 'inbound')
                        stage_import(raw,account,record['message_id'])
                        item['previous_projection']=item['projection'];item['projection']={'status':'imported','message_id_sha256':hashlib.sha256(record['message_id'].encode()).hexdigest(),'legacy_header_adjustments':changes,'scan':'prior_whole_message_scan_clean'}
                        if item['uid'] in dates:item['provider_internaldate']=dates[item['uid']]
                        save(path,item);counts['recovered']+=1
                    except Exception as error:counts[type(error).__name__]+=1
        except Exception as error:counts['provider_'+type(error).__name__]+=1
        finally:
            if client:
                try:client.logout()
                except Exception:pass
    save(ROOT/('receipt-metadata-repair-report.json' if receipt_only else 'legacy-header-repair-report.json'),{'counts':dict(counts),'provider_mutations':False,'originals_modified':False})
    print(json.dumps(dict(counts)))

if __name__=='__main__':main()
