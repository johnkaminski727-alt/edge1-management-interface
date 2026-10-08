"""Shared fail-closed mail release decisions. No message content is sent to AI.

Transport evidence is supplied by the local MTA, never Authentication-Results
headers supplied by a sender. Provider imports start with unknown SPF evidence.
"""
from __future__ import annotations
import hashlib
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import time
from urllib.parse import quote
import urllib.request

DEFAULT_DB = '/var/lib/wwcx-mail-security/security.sqlite3'
DEFAULT_POLICY = {'junk_score': 6, 'quarantine_score': 15, 'domains': {}, 'trusted_senders': []}
STATES = {'released', 'junk', 'quarantine', 'pending'}


def required():
    return os.getenv('WWCX_MAIL_SECURITY_REQUIRED') == 'true'


def database_path():
    return Path(os.getenv('WWCX_MAIL_SECURITY_DATABASE', DEFAULT_DB))


def message_hash(message_id):
    return hashlib.sha256(message_id.encode()).hexdigest()


def decision_fingerprint(decision, *, legacy=False):
    # Human release is bound to reviewed findings, never future changed findings.
    # URIBL_BLOCKED means the lookup provider denied a query, not a URL threat.
    symbols=[s for s in decision.get('symbols',[]) if legacy or s != 'URIBL_BLOCKED']
    facts={'state':decision['state'],'reasons':sorted(decision.get('reasons',[])),'symbols':sorted(symbols)}
    return hashlib.sha256(json.dumps(facts,sort_keys=True).encode()).hexdigest()


def reviewed_release_matches(override, decision):
    if override == 'reviewed_release:'+decision_fingerprint(decision):
        return True
    # Migrate existing approvals only when all findings match, allowing this
    # one diagnostic to have appeared/disappeared during periodic rescanning.
    symbols=[s for s in decision.get('symbols',[]) if s != 'URIBL_BLOCKED']
    variants=[{**decision,'symbols':symbols},{**decision,'symbols':symbols+['URIBL_BLOCKED']}]
    return any(override == 'reviewed_release:'+decision_fingerprint(v,legacy=True) for v in variants)


def attach(db):
    path = database_path()
    if not path.is_file() or path.is_symlink() or path.stat().st_mode & 0o077:
        raise RuntimeError('Private security decisions unavailable')
    db.create_function('mail_hash', 1, message_hash)
    db.execute('ATTACH DATABASE ? AS mail_security', ('file:'+quote(str(path), safe='/')+'?mode=ro',))
    db.execute('SELECT message_hash,state FROM mail_security.decisions LIMIT 0')


def release_clause(alias='correspondence'):
    return f"({alias}.direction='outbound' OR EXISTS (SELECT 1 FROM mail_security.decisions s WHERE s.message_hash=mail_hash({alias}.message_id) AND s.state='released'))"


class SecurityStore:
    def __init__(self, path=None, read_only=False):
        self.path = Path(path or database_path())
        self.read_only = read_only
        if self.path.is_symlink() or self.path.parent.is_symlink():
            raise ValueError('Unsafe security store')
        if read_only:
            if not self.path.is_file() or self.path.stat().st_mode & 0o077:
                raise RuntimeError('Private security decisions unavailable')
            return
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''
CREATE TABLE IF NOT EXISTS decisions(message_hash TEXT PRIMARY KEY, raw_hash TEXT NOT NULL, state TEXT NOT NULL, automatic_state TEXT NOT NULL, payload TEXT NOT NULL, checked REAL NOT NULL, override TEXT);
CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, message_hash TEXT NOT NULL, action TEXT NOT NULL, occurred REAL NOT NULL, interaction INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS learning(message_hash TEXT PRIMARY KEY, classification TEXT NOT NULL, updated REAL NOT NULL, completed REAL);
CREATE TABLE IF NOT EXISTS indicators(message_hash TEXT NOT NULL, kind TEXT NOT NULL, digest TEXT NOT NULL, PRIMARY KEY(message_hash,kind,digest));
CREATE TABLE IF NOT EXISTS filter_settings(domain TEXT PRIMARY KEY, payload TEXT NOT NULL);
''')
        self.path.chmod(0o600)

    def connect(self):
        return sqlite3.connect('file:'+quote(str(self.path),safe='/')+'?mode=ro',uri=True,timeout=15) if self.read_only else sqlite3.connect(self.path, timeout=15)

    def get(self, message_id):
        with self.connect() as db:
            row = db.execute('SELECT state,payload,checked,override FROM decisions WHERE message_hash=?', (message_hash(message_id),)).fetchone()
        if not row:
            return {'state': 'pending', 'reasons': ['awaiting_security_checks'], 'authentication': {'status':'not_verified'}, 'scan_complete':False}
        return {**json.loads(row[1]), 'state':row[0], 'checked_at':row[2], 'operator_report':row[3]}

    def write(self, message_id, raw_hash, decision, indicators=()):
        key = message_hash(message_id)
        if decision['state'] not in STATES: raise ValueError('Invalid security state')
        with self.connect() as db:
            old = db.execute('SELECT raw_hash,state,override,payload FROM decisions WHERE message_hash=?', (key,)).fetchone()
            if old and (old[0] not in {'unscanned',raw_hash} or 'conflicting_message_id' in json.loads(old[3]).get('reasons',[])):
                decision = {**decision, 'state':'quarantine','hard_block':True, 'reasons':['conflicting_message_id']}
            override = old[2] if old else None
            state = decision['state']
            if override in {'phishing','confirmed_phishing'}: state='quarantine'
            elif override == 'spam' and state == 'released': state='junk'
            elif override == 'not_spam' and state == 'junk' and decision.get('scan_complete') and not decision.get('hard_block'): state='released'
            elif reviewed_release_matches(override, decision) and decision.get('scan_complete') and not decision.get('hard_block') and state != 'pending':
                state='released'; override='reviewed_release:'+decision_fingerprint(decision)
            db.execute('INSERT INTO decisions VALUES (?,?,?,?,?,?,?) ON CONFLICT(message_hash) DO UPDATE SET raw_hash=excluded.raw_hash,state=excluded.state,automatic_state=excluded.automatic_state,payload=excluded.payload,checked=excluded.checked,override=excluded.override', (key,raw_hash,state,decision['state'],json.dumps(decision),time.time(),override))
            if not old or old[1] != state:
                db.execute('INSERT INTO events(message_hash,action,occurred) VALUES (?,?,?)',(key,'classified_'+state,time.time()))
            for kind, digest in indicators:
                db.execute('INSERT OR IGNORE INTO indicators VALUES (?,?,?)',(key,kind,digest))

    def action(self, message_id, action, interacted=False):
        if action not in {'spam','not_spam','phishing','confirmed_phishing','release'} or type(interacted) is not bool:
            raise ValueError('Invalid security action')
        key=message_hash(message_id)
        with self.connect() as db:
            row=db.execute('SELECT state,payload,override FROM decisions WHERE message_hash=?',(key,)).fetchone()
            if not row:
                if action not in {'phishing','confirmed_phishing'}: raise ValueError('Checks have not completed')
                payload={'state':'pending','reasons':['awaiting_security_checks'],'scan_complete':False,'hard_block':False,'authentication':{'status':'not_verified'}}
                db.execute('INSERT INTO decisions VALUES (?,?,?,?,?,?,NULL)',(key,'unscanned','pending','pending',json.dumps(payload),0))
                row=('pending',json.dumps(payload),None)
            payload=json.loads(row[1]); state=row[0]
            if action in {'not_spam','release'}:
                if action == 'not_spam' and state not in {'junk','released'}:
                    raise ValueError('Quarantine requires explicit reviewed release')
                if not payload.get('scan_complete') or payload.get('hard_block') or row[2]=='confirmed_phishing':
                    raise ValueError('Release blocked: complete checks and no hard security finding required')
                state='released'; override='not_spam' if action=='not_spam' else 'reviewed_release:'+decision_fingerprint(payload)
            elif action=='spam': state='quarantine' if state in {'quarantine','pending'} else 'junk'; override=row[2] if row[2] in {'phishing','confirmed_phishing'} else 'spam'
            else: state='quarantine'; override=action
            db.execute('UPDATE decisions SET state=?,override=? WHERE message_hash=?',(state,override,key))
            db.execute('INSERT INTO events(message_hash,action,occurred,interaction) VALUES (?,?,?,?)',(key,action,time.time(),int(interacted)))
            if action in {'spam','not_spam'} and override not in {'phishing','confirmed_phishing'}:
                db.execute('INSERT INTO learning VALUES (?,?,?,NULL) ON CONFLICT(message_hash) DO UPDATE SET classification=excluded.classification,updated=excluded.updated,completed=NULL',(key,'spam' if action=='spam' else 'ham',time.time()))
            related=db.execute('SELECT DISTINCT i.message_hash FROM indicators i JOIN indicators own ON i.kind=own.kind AND i.digest=own.digest WHERE own.message_hash=? AND i.message_hash!=? LIMIT 100',(key,key)).fetchall() if action in {'phishing','confirmed_phishing'} else []
            for (other,) in related:
                # Mark for human review; do not train or permanently block spoofed identities.
                db.execute("UPDATE decisions SET state='quarantine',override=CASE WHEN override='confirmed_phishing' THEN override ELSE 'phishing' END WHERE message_hash=?",(other,))
                db.execute('INSERT INTO events(message_hash,action,occurred) VALUES (?,?,?)',(other,'related_phishing_review',time.time()))
        return {'saved':True,'state':state,'related_flagged':len(related),'interaction_reported':interacted,'send_authorized':False}

    def settings(self, data=None):
        domains={'ww.cx','creekco.ca','spiritcreekgardens.com','scgardens.ca','omegafx.com'}
        if data is not None:
            if not isinstance(data,dict) or set(data)!={'domain','junk_score','quarantine_score','trusted_senders'} or data['domain'] not in domains:
                raise ValueError('Invalid domain settings')
            if any(type(data[k]) not in {int,float} or not math.isfinite(data[k]) for k in ['junk_score','quarantine_score']) or not 3<=data['junk_score']<data['quarantine_score']<=30:
                raise ValueError('Invalid thresholds')
            senders=data['trusted_senders']
            if not isinstance(senders,list) or len(senders)>100 or any(not isinstance(s,str) or len(s)>320 or not re.fullmatch(r'[^\s@]+@[^\s@]+',s) for s in senders): raise ValueError('Invalid trusted senders')
            with self.connect() as db:
                db.execute('INSERT INTO filter_settings VALUES (?,?) ON CONFLICT(domain) DO UPDATE SET payload=excluded.payload',(data['domain'],json.dumps({k:v for k,v in data.items() if k!='domain'})))
                db.execute('INSERT INTO events(message_hash,action,occurred) VALUES (?,?,?)',('settings','filter_settings_changed',time.time()))
        with self.connect() as db:
            saved={domain:json.loads(payload) for domain,payload in db.execute('SELECT domain,payload FROM filter_settings')}
        return {'domains':{d:{**DEFAULT_POLICY,**saved.get(d,{})} for d in sorted(domains)},'trust_requires_dmarc':True,'security_checks_bypassed':False}


def rspamd_scan(raw, transport=None):
    headers={'Content-Type':'message/rfc822','Flags':'pass_all,no_log','Log':'no'}
    # Only out-of-band metadata written by our Postfix pipe is accepted.
    if transport and transport.get('source')=='postfix_pipe':
        address=str(ipaddress.ip_address(transport['client_ip']))
        sender=transport.get('envelope_sender','')
        if any(c in sender for c in '\r\n') or len(sender)>320: raise ValueError('Invalid envelope')
        headers.update({'IP':address,'From':sender})
    else:
        headers['Settings']=json.dumps({'symbols_disabled':['SPF_CHECK']})
    request=urllib.request.Request('http://127.0.0.1:11333/checkv2',data=raw,headers=headers)
    with urllib.request.urlopen(request,timeout=45) as response:
        result=json.loads(response.read(1024*1024))
    if (result.get('is_skipped') and result.get('action') not in {'reject','quarantine'}) or not isinstance(result.get('symbols'),dict) or not isinstance(result.get('score'),(int,float)) or not math.isfinite(result['score']):
        raise ValueError('Incomplete spam scan')
    return result


def verified_local_submission(transport, sender, policy):
    """Trust private MTA evidence and approved local services, never mail headers alone."""
    if not transport or transport.get('source') != 'postfix_pipe': return False
    try:
        if not ipaddress.ip_address(transport.get('client_ip', '')).is_loopback: return False
    except ValueError: return False
    address=sender.strip().lower()
    if not re.fullmatch(r'[^@\s<>]+@[^@\s<>]+', address): return False
    return (transport.get('envelope_sender', '').strip().lower() == address
            and address.rsplit('@', 1)[1] in (policy or {}).get('local_submission_domains', []))


def classify(result, attachment_states, *, transport=None, domain='', policy=None, verified_local=False):
    policy=policy or DEFAULT_POLICY
    limits={**DEFAULT_POLICY,**policy,**policy.get('domains',{}).get(domain,{})}
    symbols=set(result['symbols']); reasons=[]
    trusted_ip=bool(transport and transport.get('source')=='postfix_pipe' and transport.get('client_ip'))
    auth={'status':'domain_authenticated' if 'DMARC_POLICY_ALLOW' in symbols else 'authentication_failed' if symbols & {'DMARC_POLICY_REJECT','DMARC_POLICY_QUARANTINE'} else 'not_verified',
          'spf':'pass' if trusted_ip and 'R_SPF_ALLOW' in symbols else 'fail' if trusted_ip and 'R_SPF_FAIL' in symbols else 'not_verified',
          'dkim':'pass' if 'R_DKIM_ALLOW' in symbols else 'fail' if 'R_DKIM_REJECT' in symbols else 'not_verified',
          'dmarc':'pass' if 'DMARC_POLICY_ALLOW' in symbols else 'fail' if symbols & {'DMARC_POLICY_REJECT','DMARC_POLICY_QUARANTINE'} else 'not_verified',
          'connection_evidence':'trusted_mta' if trusted_ip else 'unavailable', 'person_verified':False}
    # Imported mail has no observed SMTP IP: SPF-only inferred results cannot authenticate it.
    if not trusted_ip and 'R_DKIM_ALLOW' not in symbols and auth['dmarc']=='pass':
        auth.update(status='not_verified',dmarc='not_verified')
    blocked=any(s in {'quarantined','oversize_blocked','policy_blocked'} for s in attachment_states)
    incomplete=any(s=='unscanned_blocked' for s in attachment_states)
    phishing=bool(symbols & {'PHISHING','PHISHING_DUMMY','DMARC_POLICY_REJECT','DMARC_POLICY_QUARANTINE'})
    state='released'
    if blocked: state='quarantine'; reasons.append('attachment_security_block')
    elif incomplete: state='pending'; reasons.append('attachment_scan_incomplete')
    elif result.get('is_skipped'): state='quarantine'; reasons.append('filter_rejected_before_all_checks'); incomplete=True
    elif symbols & {'R_SPF_DNSFAIL','DKIM_TEMPFAIL','DMARC_DNSFAIL'}: state='pending'; reasons.append('authentication_check_unavailable'); incomplete=True
    elif phishing: state='quarantine'; reasons.append('phishing_or_sender_authentication_failure')
    elif result.get('action') == 'quarantine': state='quarantine'; reasons.append('filter_quarantine')
    elif result['score']>=limits['quarantine_score']: state='quarantine'; reasons.append('high_spam_score')
    elif verified_local and result.get('action') not in {'reject','soft reject','greylist','quarantine'} and not symbols & {'GTUBE','GTUBE_REJECT','SPAM_TEST'}: reasons.append('verified_local_submission')
    elif result['score']>=limits['junk_score'] or result.get('action') in {'add header','rewrite subject','reject'}: state='junk'; reasons.append('likely_spam')
    elif result.get('action') in {'soft reject','greylist'}: state='pending'; reasons.append('temporary_filter_hold')
    return {'state':state,'score':result['score'],'reasons':reasons or ['checks_passed'], 'symbols':sorted(symbols)[:128], 'authentication':auth,'scan_complete':not incomplete,'hard_block':blocked,'downloads_enabled':False}


def archive_message_id(raw, item):
    from email import policy
    from email.parser import BytesParser
    original=str(BytesParser(policy=policy.default).parsebytes(raw,headersonly=True).get('Message-ID','')).strip()
    projected=item.get('normalization',{}).get('indexed_message_id')
    if projected is None:return original
    expected='<privateemail-'+hashlib.sha256(raw).hexdigest()+'@archive.ww.cx>'
    if item.get('source')!='namecheap-private-email-imap' or projected!=expected:
        raise ValueError('Invalid archival message identity')
    return projected


def stage_provider(raw, recipient, message_id, provider_source="namecheap-private-email-imap"):
    """Archive imported originals for the identical inspection/review pipeline."""
    from datetime import datetime, timezone
    root=Path('/var/lib/wwcx-mail-gateway/inbound')
    domain=recipient.rsplit('@',1)[1].lower()
    if not re.fullmatch(r'[a-z0-9.-]{1,253}',domain): raise ValueError('Invalid provider domain')
    digest=hashlib.sha256(raw).hexdigest()
    directory=root/domain/('imap-'+digest[:24])
    directory.mkdir(mode=0o700,parents=True,exist_ok=True)
    if directory.is_symlink(): raise ValueError('Unsafe provider archive')
    from email import policy
    from email.parser import BytesParser
    original=str(BytesParser(policy=policy.default).parsebytes(raw,headersonly=True).get('Message-ID','')).strip()
    normalization={'message_id_sha256':message_hash(message_id)}
    if original!=message_id:
        if provider_source!='namecheap-private-email-imap' or message_id!='<privateemail-'+digest+'@archive.ww.cx>':raise ValueError('Invalid archival message identity')
        normalization['indexed_message_id']=message_id
    for filename,content in [('message.eml',raw),('metadata.json',(json.dumps({'contract':'wwcx.provider-mail-security-archive.v1','domain':domain,'envelope_recipient':recipient,'archived_at':datetime.now(timezone.utc).isoformat(),'rfc822_sha256':digest,'normalization':normalization,'source':provider_source})+'\n').encode())]:
        target=directory/filename
        if target.is_symlink(): raise ValueError('Unsafe provider archive file')
        if target.exists(): continue
        fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'wb') as f: f.write(content); f.flush(); os.fsync(f.fileno())
