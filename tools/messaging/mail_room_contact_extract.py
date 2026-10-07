#!/usr/bin/env python3
"""Extract evidence-backed contact candidates from released Mail Room messages.

Candidate-only: this tool never writes Unified Contacts production records. It writes
an idempotent candidate ledger consumed by the Contacts Maintenance bot.
"""
from __future__ import annotations
import argparse, email, hashlib, json, os, re, sqlite3, subprocess, tempfile, zipfile
from datetime import datetime, timezone
from email import policy
from email.utils import parseaddr
from pathlib import Path
from urllib.parse import urlsplit
from xml.etree import ElementTree as ET

MAIL_DB=Path('/var/lib/wwcx-mail-room/correspondence.sqlite3')
SECURITY_DB=Path('/var/lib/wwcx-mail-security/security.sqlite3')
DRAFT_DB=Path('/var/lib/wwcx-mail-room-drafts/drafts.sqlite3')
ARCHIVE_ROOT=Path('/var/lib/wwcx-mail-gateway/inbound')
STATE_DB=Path('/var/lib/edge1-contacts-maintenance/maintenance.sqlite')
INTEL_ROOT=Path('/var/lib/wwcx-mail-intelligence')
IDENTITY_REGISTRY=Path(__file__).resolve().parents[2]/'config/messaging/mail-identities.json'
MAX_ATTACHMENT=12*1024*1024
MAX_ATTACHMENT_TEXT=24000

SCHEMA='''
CREATE TABLE IF NOT EXISTS mail_contact_extractions(
 id INTEGER PRIMARY KEY AUTOINCREMENT, fingerprint TEXT NOT NULL UNIQUE,
 message_id TEXT NOT NULL, message_sha256 TEXT NOT NULL, occurred_at TEXT,
 sender TEXT, subject TEXT, direction TEXT, sender_owned INTEGER NOT NULL DEFAULT 0, security_state TEXT NOT NULL, reviewed INTEGER NOT NULL DEFAULT 0,
 extracted_at TEXT NOT NULL, attachment_count INTEGER NOT NULL DEFAULT 0,
 candidate_count INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'staged'
);
CREATE TABLE IF NOT EXISTS mail_contact_candidates(
 id INTEGER PRIMARY KEY AUTOINCREMENT, fingerprint TEXT NOT NULL UNIQUE,
 extraction_id INTEGER NOT NULL REFERENCES mail_contact_extractions(id) ON DELETE CASCADE,
 candidate_type TEXT NOT NULL, normalized_value TEXT NOT NULL, display_value TEXT NOT NULL,
 confidence TEXT NOT NULL, source_kind TEXT NOT NULL, source_reference TEXT NOT NULL,
 context TEXT, attachment_sha256 TEXT, status TEXT NOT NULL DEFAULT 'pending',
 matched_entity_id INTEGER, matched_contact_point_id INTEGER, created_at TEXT NOT NULL,
 UNIQUE(extraction_id,candidate_type,normalized_value,source_reference)
);
CREATE INDEX IF NOT EXISTS idx_mail_contact_candidate_status ON mail_contact_candidates(status,candidate_type);
CREATE INDEX IF NOT EXISTS idx_mail_contact_extraction_message ON mail_contact_extractions(message_id,extracted_at);
CREATE TABLE IF NOT EXISTS mail_attachment_intelligence(
 attachment_sha256 TEXT PRIMARY KEY, message_id TEXT NOT NULL, filename TEXT NOT NULL,
 mime_type TEXT, text_path TEXT, extracted_chars INTEGER NOT NULL DEFAULT 0,
 state TEXT NOT NULL, analyzed_at TEXT NOT NULL
);
'''
EMAIL_RE=re.compile(r'(?<![\w.+-])([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,63})(?![\w.-])',re.I)
URL_RE=re.compile(r'https?://[^\s<>"\']+',re.I)
PHONE_RE=re.compile(r'(?<!\d)(\+?\d[\d().\-\s]{6,}\d)(?!\d)')
POSTAL_RE=re.compile(r'\b([ABCEGHJ-NPRSTVXY]\d[ABCEGHJ-NPRSTVWXYZ][ -]?\d[ABCEGHJ-NPRSTVWXYZ]\d)\b',re.I)
TITLE_WORDS=('director','manager','president','vice president','owner','founder','coordinator','administrator','representative','officer','accountant','lawyer','counsel')

def utcnow(): return datetime.now(timezone.utc).isoformat(timespec='seconds')
def _ensure_column(db, table, definition):
    name=definition.split()[0]
    columns={r[1] for r in db.execute(f'PRAGMA table_info({table})')}
    if name not in columns: db.execute(f'ALTER TABLE {table} ADD COLUMN {definition}')
def managed_mail_domains(path=IDENTITY_REGISTRY):
    try:
        data=json.loads(Path(path).read_text())
        return {str(x).strip().casefold() for x in (data.get('domains') or {}) if str(x).strip()}
    except Exception:
        return set()
def sender_is_owned(sender, domains):
    address=parseaddr(str(sender or ''))[1].strip().casefold()
    return bool('@' in address and address.rsplit('@',1)[1] in domains)
def sha(s): return hashlib.sha256(s.encode()).hexdigest()
def norm_phone(v):
    v=v.strip(); digits=re.sub(r'\D','',v)
    if len(digits)<7 or len(digits)>15: return None
    return ('+' if v.startswith('+') else '')+digits


def plausible_phone_candidate(raw, context=''):
    """Reject numeric tokens that merely look phone-like.

    The mail extractor sees tracking tokens, IP addresses, booking numbers and
    timestamps. International numbers carrying an explicit + are allowed;
    plain North-American numbers must satisfy NANP structure; shorter/plain
    numbers require nearby phone-oriented language.
    """
    raw=str(raw or '').strip(); context=str(context or '')
    digits=re.sub(r'\D','',raw)
    low=context.casefold()
    pos=context.find(raw)
    before=(context[max(0,pos-50):pos] if pos >= 0 else context[:50]).casefold()
    phone_words=('phone','telephone','tel:','mobile','cell','fax','call','contact details','contact number')
    obvious_noise=('ip address','confirmation number','confirmation:','pin code','tracking_pixel','token=','key=','alert/nt/','order number','invoice number')
    if any(x in low for x in obvious_noise) and not any(x in before for x in phone_words):
        return False
    if re.fullmatch(r'\d{1,3}(?:\.\d{1,3}){3}', raw):
        return False
    if raw.startswith('+'):
        return 8 <= len(digits) <= 15
    if len(digits)==10:
        return digits[0] in '23456789' and digits[3] in '23456789'
    if len(digits)==11 and digits.startswith('1'):
        return digits[1] in '23456789' and digits[4] in '23456789'
    if any(x in before for x in phone_words):
        return 7 <= len(digits) <= 15 and len(set(digits)) > 2
    return False

def safe_excerpt(v,n=500):
    return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]+',' ',str(v or '')).strip()[:n]

def archive_index(root:Path):
    out={}
    if not root.is_dir(): return out
    for meta in root.glob('*/*/metadata.json'):
        try:
            data=json.loads(meta.read_text())
            key=data.get('normalization',{}).get('message_id_sha256')
            raw=meta.with_name('message.eml')
            if key and raw.is_file() and raw.stat().st_size<=40*1024*1024: out[key]=raw
        except Exception: pass
    return out

def attachment_states(db_path:Path,message_id:str):
    try:
        with sqlite3.connect(f'file:{db_path}?mode=ro',uri=True) as db:
            row=db.execute('SELECT payload FROM attachment_checks WHERE message_hash=?',(sha(message_id),)).fetchone()
        if not row:return {}
        data=json.loads(row[0]); return {x.get('sha256'):x.get('state') for x in data.get('attachments',[]) if x.get('sha256')}
    except Exception:return {}

def zip_text(data:bytes,kind:str):
    if len(data)>MAX_ATTACHMENT:return ''
    try:
        with tempfile.NamedTemporaryFile(suffix='.'+kind) as f:
            f.write(data);f.flush()
            with zipfile.ZipFile(f.name) as z:
                names=z.namelist()
                targets=[n for n in names if (kind=='docx' and n.startswith('word/') and n.endswith('.xml')) or (kind=='xlsx' and (n.startswith('xl/sharedStrings') or n.startswith('xl/worksheets/')) and n.endswith('.xml'))]
                text=[]
                for name in targets[:40]:
                    raw=z.read(name)
                    if len(raw)>2*1024*1024:continue
                    root=ET.fromstring(raw)
                    text.extend(t.text for t in root.iter() if t.text)
                return ' '.join(text)[:MAX_ATTACHMENT_TEXT]
    except Exception:return ''

def pdf_text(data:bytes):
    if len(data)>MAX_ATTACHMENT or not Path('/usr/bin/pdftotext').exists(): return ''
    try:
        with tempfile.TemporaryDirectory(prefix='mail-contact-pdf-') as d:
            src=Path(d)/'a.pdf'; dst=Path(d)/'a.txt'; src.write_bytes(data);src.chmod(0o600)
            r=subprocess.run(['/usr/bin/pdftotext','-q',str(src),str(dst)],timeout=20,check=False,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            return dst.read_text(errors='replace')[:MAX_ATTACHMENT_TEXT] if r.returncode==0 and dst.is_file() else ''
    except Exception:return ''

def safe_attachment_text(raw_path:Path,message_id:str,states:dict):
    results=[]
    if not raw_path:return results
    try: msg=email.message_from_bytes(raw_path.read_bytes(),policy=policy.default)
    except Exception:return results
    for part in msg.walk():
        if part.is_multipart() or not (part.get_filename() or part.get_content_disposition()=='attachment'):continue
        data=part.get_payload(decode=True) or b''
        digest=hashlib.sha256(data).hexdigest()
        if states.get(digest)!='clean_download_disabled' or len(data)>MAX_ATTACHMENT:continue
        name=safe_excerpt(part.get_filename() or 'attachment',180); ctype=part.get_content_type().lower(); ext=Path(name).suffix.lower()
        text=''
        try:
            if ctype.startswith('text/') or ext in {'.txt','.csv','.vcf','.ics'}: text=data.decode(part.get_content_charset() or 'utf-8',errors='replace')[:MAX_ATTACHMENT_TEXT]
            elif ctype=='application/pdf' or ext=='.pdf': text=pdf_text(data)
            elif ext=='.docx': text=zip_text(data,'docx')
            elif ext=='.xlsx': text=zip_text(data,'xlsx')
        except Exception:text=''
        results.append({'filename':name,'sha256':digest,'text':text,'type':ctype})
    return results

def extract_candidates(sender,body,attachments):
    candidates=[]
    def add(kind,value,display,confidence,source,ref,context='',ash=None):
        candidates.append({'type':kind,'value':value,'display':display,'confidence':confidence,'source_kind':source,'source_reference':ref,'context':safe_excerpt(context),'attachment_sha256':ash})
    sender_name,sender_addr=parseaddr(sender or '')
    if sender_addr and '@' in sender_addr:
        addr=sender_addr.lower(); add('email',addr,addr,'high','message_header','sender',sender)
        domain=addr.rsplit('@',1)[1]; add('domain',domain,domain,'medium','message_header','sender_domain',sender)
    if sender_name.strip(): add('person_name',' '.join(sender_name.split()),sender_name.strip(),'medium','message_header','sender_display',sender)
    texts=[('message_body','body',body,None)]+[('attachment',a['filename'],a.get('text',''),a['sha256']) for a in attachments if a.get('text')]
    for source,ref,text,ash in texts:
        if not text:continue
        for m in EMAIL_RE.finditer(text):
            v=m.group(1).lower(); add('email',v,v,'medium',source,ref,text[max(0,m.start()-100):m.end()+100],ash)
        for m in PHONE_RE.finditer(text):
            raw=m.group(1).strip()
            context=text[max(0,m.start()-100):m.end()+100]
            n=norm_phone(raw)
            if n and plausible_phone_candidate(raw,context):
                add('phone',n,raw,'medium',source,ref,context,ash)
        for m in URL_RE.finditer(text):
            url=m.group(0).rstrip('.,);]')
            try:
                parsed=urlsplit(url)
                host=(parsed.hostname or '').lower()
                clean_host=re.sub(r'^www\.','',host)
                shallow_path=parsed.path in ('','/') or (parsed.path.count('/') <= 1 and len(parsed.path) <= 48)
                if not clean_host or '.' not in clean_host or parsed.query or parsed.fragment or not shallow_path:
                    continue
                website=f'{parsed.scheme.lower()}://{host}' + ('/' if parsed.path=='/' else parsed.path)
                add('website',website.lower(),website,'medium',source,ref,text[max(0,m.start()-80):m.end()+80],ash)
                add('domain',clean_host,clean_host,'medium',source,ref,website,ash)
            except Exception:
                continue
        for m in POSTAL_RE.finditer(text):
            lines=text[max(0,m.start()-160):m.end()+40].splitlines(); street=next((x.strip() for x in reversed(lines[:-1]) if re.search(r'\d+\s+\S+',x)), '')
            val=(' '.join([street,m.group(1).upper()])).strip(); add('postal_address',val,val,'low',source,ref,val,ash)
        lines=[x.strip() for x in text.splitlines() if x.strip()]
        for i,line in enumerate(lines[-18:]):
            low=line.casefold()
            if 2<=len(line.split())<=9 and any(t in low for t in TITLE_WORDS): add('job_title',line.casefold(),line,'low',source,ref,line,ash)
    unique={}
    for c in candidates:
        key=(c['type'],c['value'],c['source_reference'],c['attachment_sha256'])
        unique.setdefault(key,c)
    return list(unique.values())

def run(mail_db=MAIL_DB,security_db=SECURITY_DB,draft_db=DRAFT_DB,state_db=STATE_DB,archive_root=ARCHIVE_ROOT,intel_root=INTEL_ROOT,limit=5000):
    for p in (mail_db,security_db,draft_db):
        if not Path(p).is_file(): raise RuntimeError(f'missing source: {p}')
    idx=archive_index(Path(archive_root)); now=utcnow(); processed=0; staged=0; attachments_seen=0
    state=sqlite3.connect(state_db); state.row_factory=sqlite3.Row; state.execute('PRAGMA foreign_keys=ON'); state.executescript(SCHEMA); _ensure_column(state,'mail_contact_extractions','direction TEXT'); _ensure_column(state,'mail_contact_extractions','sender_owned INTEGER NOT NULL DEFAULT 0')
    mail=sqlite3.connect(f'file:{mail_db}?mode=ro',uri=True); mail.row_factory=sqlite3.Row
    sec=sqlite3.connect(f'file:{security_db}?mode=ro',uri=True); sec.row_factory=sqlite3.Row
    domains=managed_mail_domains(); rows=mail.execute("SELECT message_id,sender,subject,body_text,occurred_at,direction FROM correspondence WHERE direction='inbound' AND source_authoritative=1 AND source_scope IN ('local_native','production_native') ORDER BY julianday(occurred_at) DESC,message_id DESC LIMIT ?",(limit,)).fetchall()
    for r in rows:
        key=sha(r['message_id']); decision=sec.execute('SELECT state,override FROM decisions WHERE message_hash=?',(key,)).fetchone()
        if not decision or decision['state']!='released': continue
        reviewed=bool(decision['override'] and (str(decision['override']).startswith('reviewed_release:') or decision['override']=='not_spam'))
        fingerprint=sha('|'.join([r['message_id'],hashlib.sha256((r['body_text'] or '').encode()).hexdigest(),decision['state'],str(reviewed)]))
        old=state.execute('SELECT id FROM mail_contact_extractions WHERE fingerprint=?',(fingerprint,)).fetchone()
        if old: continue
        atts=safe_attachment_text(idx.get(key),r['message_id'],attachment_states(Path(draft_db),r['message_id'])); attachments_seen+=len(atts)
        attachment_dir=Path(intel_root)/'attachments'; attachment_dir.mkdir(mode=0o700,parents=True,exist_ok=True)
        for a in atts:
            text=a.get('text',''); text_path=None; state_name='metadata_only'
            if text:
                target=attachment_dir/(a['sha256']+'.txt'); temp=target.with_suffix('.tmp')
                temp.write_text(text,errors='replace'); temp.chmod(0o600); temp.replace(target)
                text_path=str(target); state_name='text_extracted'
            state.execute('''INSERT INTO mail_attachment_intelligence(attachment_sha256,message_id,filename,mime_type,text_path,extracted_chars,state,analyzed_at) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(attachment_sha256) DO UPDATE SET message_id=excluded.message_id,filename=excluded.filename,mime_type=excluded.mime_type,text_path=excluded.text_path,extracted_chars=excluded.extracted_chars,state=excluded.state,analyzed_at=excluded.analyzed_at''',(a['sha256'],r['message_id'],a['filename'],a['type'],text_path,len(text),state_name,now))
        candidates=extract_candidates(r['sender'],r['body_text'] or '',atts)
        cur=state.execute('''INSERT INTO mail_contact_extractions(fingerprint,message_id,message_sha256,occurred_at,sender,subject,direction,sender_owned,security_state,reviewed,extracted_at,attachment_count,candidate_count) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',(fingerprint,r['message_id'],key,r['occurred_at'],safe_excerpt(r['sender'],320),safe_excerpt(r['subject'],500),r['direction'],int(sender_is_owned(r['sender'],domains)),decision['state'],int(reviewed),now,len(atts),len(candidates)))
        eid=cur.lastrowid
        for c in candidates:
            cf=sha('|'.join([fingerprint,c['type'],c['value'],c['source_reference'],c.get('attachment_sha256') or '']))
            state.execute('''INSERT OR IGNORE INTO mail_contact_candidates(fingerprint,extraction_id,candidate_type,normalized_value,display_value,confidence,source_kind,source_reference,context,attachment_sha256,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)''',(cf,eid,c['type'],c['value'],c['display'],c['confidence'],c['source_kind'],c['source_reference'],c['context'],c['attachment_sha256'],now))
        processed+=1; staged+=len(candidates)
    state.commit(); mail.close();sec.close();state.close()
    os.chown(state_db, __import__('pwd').getpwnam('wwadmin').pw_uid, __import__('grp').getgrnam('wwadmin').gr_gid); os.chmod(state_db,0o660)
    return {'messages_processed':processed,'candidates_staged':staged,'attachments_analyzed':attachments_seen,'candidate_only':True,'production_contacts_mutated':False}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--json',action='store_true');ap.add_argument('--limit',type=int,default=5000);a=ap.parse_args();result=run(limit=max(1,min(a.limit,5000)));print(json.dumps(result,sort_keys=True) if a.json else result)
if __name__=='__main__':main()
