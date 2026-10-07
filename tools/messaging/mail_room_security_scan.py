#!/usr/bin/env python3
"""Private archive security worker. Releases only completed inspections.

No active URL fetching, cloud content scanning, public sample uploads or AI calls.
Archived originals remain private. Missing transport evidence is never fabricated.
"""
from email import policy
from email.parser import BytesParser
from email.utils import getaddresses
import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import time
import urllib.request
from urllib.parse import urlsplit
import re
import unicodedata
from difflib import SequenceMatcher

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from server.mail_room_security import archive_message_id, SecurityStore, classify, rspamd_scan, message_hash
from tools.messaging.mail_room_attachment_scan import scan_bytes, scanner_ready

BLOCKED_EXTENSIONS={'.exe','.com','.scr','.bat','.cmd','.ps1','.vbs','.js','.jse','.wsf','.msi','.hta','.lnk','.iso','.img','.docm','.xlsm','.pptm','.xlam','.xll'}


def inspect(raw, transport=None, domain='', policy_config=None, scan=scan_bytes, spam_scan=rspamd_scan):
    pending={'state':'pending','reasons':['security_scan_unavailable'],'authentication':{'status':'not_verified'},'scan_complete':False,'hard_block':False,'downloads_enabled':False}
    if len(raw)>30*1024*1024: return {**pending,'state':'quarantine','hard_block':True,'reasons':['message_size_limit']},[],[]
    message=BytesParser(policy=policy.default).parsebytes(raw)
    attachments=[]; indicators=[]
    # All leaf parts, including inline binary and attached message bodies, are inspected.
    parts=[p for p in message.walk() if not p.is_multipart()]
    if len(parts)>60 or message.defects:
        return {**pending,'state':'quarantine','hard_block':True,'reasons':['malformed_or_excessive_mime']},[],[]
    for part in parts:
        data=part.get_payload(decode=True) or b''
        filename=''.join(c for c in (part.get_filename() or 'inline part') if ord(c)>=32)[:180]
        if part.get_filename() or part.get_content_disposition()=='attachment' or not part.get_content_type().startswith('text/'):
            executable=data.startswith((b'MZ',b'\x7fELF')) or part.get_content_type() in {'application/javascript','application/x-msdownload','application/x-executable','application/x-dosexec'}
            state='policy_blocked' if executable or Path(filename.lower()).suffix in BLOCKED_EXTENSIONS else 'oversize_blocked' if len(data)>25*1024*1024 else scan(data)
            digest=hashlib.sha256(data).hexdigest()
            attachments.append({'filename':filename,'size_bytes':len(data),'sha256':digest,'state':state})
            indicators.append(('attachment',digest))
        if part.get_content_type() in {'text/plain','text/html'}:
            for url in re.findall(r'https?://[^\s<>"\x27]+',data.decode('utf-8','replace'))[:100]:
                # Hash exact links; a shared hosting domain alone is too broad for related holds.
                indicators.append(('url',hashlib.sha256(url.encode()).hexdigest()))
    sender=getaddresses(message.get_all('From',[]))
    if len(sender)==1:
        indicators.append(('sender',hashlib.sha256(sender[0][1].lower().encode()).hexdigest()))
    # Whole RFC822 scan catches inline text signatures (including harmless EICAR canaries).
    whole=scan(raw)
    try:
        result=spam_scan(raw,transport)
        configured=(policy_config or {}).get('domains',{}).get(domain,{})
        trusted=configured.get('trusted_senders',[])
        if len(sender)==1 and sender[0][1].lower() in {s.lower() for s in trusted} and 'DMARC_POLICY_ALLOW' in result['symbols'] and 'R_DKIM_ALLOW' in result['symbols']:
            # Small scoring adjustment only; phishing/authentication/file holds remain authoritative.
            result={**result,'score':result['score']-2}
        decision=classify(result,[whole,*[a['state'] for a in attachments]],transport=transport,domain=domain,policy=policy_config)
        protected={'john kaminski','spirit creek gardens','creekco','omegafx','ww.cx'}
        managed={'ww.cx','creekco.ca','spiritcreekgardens.com','scgardens.ca','omegafx.com'}
        if len(sender)==1:
            name,address=sender[0]; from_domain=address.rsplit('@',1)[-1].lower()
            name=unicodedata.normalize('NFKC',name).casefold().strip()
            authenticated_external=(address.lower() in {a.lower() for a in (policy_config or {}).get('authenticated_external_identities',[])} and decision['authentication'].get('dkim')=='pass' and decision['authentication'].get('dmarc')=='pass')
            impersonation=name in protected and from_domain not in managed and not authenticated_external
            lookalike=from_domain not in managed and any(SequenceMatcher(None,from_domain,d).ratio()>=0.9 for d in managed)
            if impersonation or lookalike:
                decision['reasons'].append('protected_display_name_impersonation' if impersonation else 'lookalike_managed_domain')
                if decision['state']!='pending': decision['state']='quarantine'
        if message.get_all('Reply-To'):
            replies=getaddresses(message.get_all('Reply-To'))
            if len(sender)==1 and any(a.rsplit('@',1)[-1].lower()!=sender[0][1].rsplit('@',1)[-1].lower() for _,a in replies):
                decision['reasons'].append('reply_to_domain_differs')
        decision['engine']='rspamd+clamav'
    except Exception:
        decision=pending
        if whole in {'quarantined','policy_blocked','oversize_blocked'} or any(a['state'] in {'quarantined','policy_blocked','oversize_blocked'} for a in attachments):
            decision={**pending,'state':'quarantine','hard_block':True,'reasons':['attachment_or_message_security_block']}
    return decision,attachments,indicators


def process(root, security, drafts, policy_config=None):
    checked=0; errors=0
    # Older backlog cannot starve behind already-checked new messages.
    for metadata in sorted(root.glob('*/*/metadata.json'),key=lambda p:p.stat().st_mtime)[:10000]:
        if checked>=20: break
        try:
            if metadata.is_symlink() or metadata.stat().st_size>65536: continue
            item=json.loads(metadata.read_text()); raw_path=metadata.parent/'message.eml'
            if item.get('normalization',{}).get('duplicate_of'): continue
            if raw_path.is_symlink() or not raw_path.is_file(): continue
            with security.connect() as db:
                old=db.execute('SELECT checked,state FROM decisions WHERE message_hash=?',(item.get('normalization',{}).get('message_id_sha256'),)).fetchone()
            if old and old[0]>time.time()-(60 if old[1]=='pending' else 3600): continue
            # Hash mismatch never leaves an earlier released decision in place.
            if raw_path.stat().st_size>30*1024*1024:
                raw=raw_path.read_bytes()[:65536]; invalid=True
            else: raw=raw_path.read_bytes(); invalid=False
            digest=hashlib.sha256(raw).hexdigest(); invalid |= digest!=item.get('rfc822_sha256')
            message=BytesParser(policy=policy.default).parsebytes(raw,headersonly=True)
            mid=archive_message_id(raw,item)
            key=message_hash(mid)
            if key!=item.get('normalization',{}).get('message_id_sha256'): continue
            if invalid:
                decision={'state':'quarantine','reasons':['archive_integrity_or_size_failure'],'scan_complete':False,'hard_block':True,'authentication':{'status':'not_verified'}}; attachments=[]; indicators=[]
            else:
                decision,attachments,indicators=inspect(raw,item.get('transport'),item.get('domain',''),policy_config)
                allowed=(policy_config or {}).get('allowed_recipients',[])
                recipient=item.get('envelope_recipient','').lower()
                catch_all=recipient.rsplit('@',1)[-1] in (policy_config or {}).get('catch_all_domains',[])
                if allowed and not catch_all and recipient not in {a.lower() for a in allowed} and decision['state']=='released':
                    decision['state']='quarantine';decision['reasons'].append('unregistered_catch_all_recipient_review')
            security.write(mid,digest,decision,indicators)
            with sqlite3.connect(drafts,timeout=15) as db:
                payload={'attachments':attachments,'downloads_enabled':False,'quarantined':decision['state']=='quarantine','scanner_ready':scanner_ready(),'checked_at':time.time(),'indexed':True}
                db.execute('CREATE TABLE IF NOT EXISTS attachment_checks(message_hash TEXT PRIMARY KEY,archive_hash TEXT NOT NULL,payload TEXT NOT NULL,checked REAL NOT NULL)')
                db.execute('INSERT INTO attachment_checks VALUES (?,?,?,?) ON CONFLICT(message_hash) DO UPDATE SET archive_hash=excluded.archive_hash,payload=excluded.payload,checked=excluded.checked',(key,digest,json.dumps(payload),time.time()))
            checked+=1
        except (ValueError,OSError,sqlite3.Error): errors+=1
    return {'checked':checked,'errors':errors}


def learn(root, security, password):
    with security.connect() as db:
        rows=db.execute('SELECT message_hash,classification,updated FROM learning WHERE completed IS NULL LIMIT 20').fetchall()
    pending={r[0]:r for r in rows}; learned=0
    if not pending: return learned
    for meta in root.glob('*/*/metadata.json'):
        item=json.loads(meta.read_text());key=item.get('normalization',{}).get('message_id_sha256')
        if key not in pending: continue
        raw_path=meta.parent/'message.eml'
        if raw_path.is_symlink() or raw_path.stat().st_size>30*1024*1024: continue
        raw=raw_path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=item.get('rfc822_sha256'): continue
        _,kind,updated=pending[key]
        try:
            req=urllib.request.Request('http://127.0.0.1:11334/learn'+kind,data=raw,headers={'Password':password,'Content-Type':'message/rfc822','Flags':'no_log'})
            with urllib.request.urlopen(req,timeout=30) as response: result=json.loads(response.read(65536))
            if not result.get('success'): continue
            with security.connect() as db:
                db.execute('UPDATE learning SET completed=? WHERE message_hash=? AND updated=?',(time.time(),key,updated))
            learned+=1
        except Exception: pass
        del pending[key]
    return learned


def main():
    p=argparse.ArgumentParser();p.add_argument('--archive-root',type=Path,default=Path('/var/lib/wwcx-mail-gateway/inbound'));p.add_argument('--drafts',type=Path,default=Path('/var/lib/wwcx-mail-room-drafts/drafts.sqlite3'));a=p.parse_args()
    os.umask(0o077);security=SecurityStore();config_path=Path('/etc/wwcx/mail-security-policy.json');config=json.loads(config_path.read_text())
    config['domains']={**config.get('domains',{}),**security.settings()['domains']}
    identities=json.loads(Path('/etc/wwcx/outbound-mail/identities.json').read_text())
    config['allowed_recipients']=list(identities['sender_selection']['recipient_to_sender']) + [v['address'] for v in identities['sender_profiles'].values()]
    config['catch_all_domains']=list(identities.get('catch_all_domains',{}))
    result=process(a.archive_root,security,a.drafts,config)
    result['learned']=learn(a.archive_root,security,os.environ.get('WWCX_RSPAMD_CONTROLLER_PASSWORD',''))
    print(json.dumps(result))

if __name__=='__main__': main()
